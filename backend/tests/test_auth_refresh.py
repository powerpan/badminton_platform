"""Refresh regression: real JWT/HTTP/owned Redis, fixture user reads, no MySQL."""
from dataclasses import replace
from datetime import datetime, timezone
import json
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, patch

import jwt
from tornado.testing import AsyncHTTPTestCase, gen_test
from tornado.web import Application

from config.settings import load_settings
from routes import build_routes
from services import auth_service, redis_service
from utils.response import ApiError
from utils.tokens import (
    create_access_token, create_refresh_token, decode_access_token, decode_refresh_token,
)


SECRET = 'refresh-regression-fixture-only'
TOKEN_ARGS = dict(user_id=7, username='refresh_fixture', role='user', secret=SECRET,
                  expire_seconds=300)


class RefreshDecoderTests(unittest.TestCase):
    def test_valid_refresh_token_is_accepted(self):
        token = create_refresh_token(**TOKEN_ARGS, token_id='session-one')
        payload = decode_refresh_token(token, SECRET)
        self.assertEqual(payload['user_id'], 7)
        self.assertEqual(payload['token_type'], 'refresh')
        self.assertEqual(payload['token_id'], 'session-one')

    def test_token_types_and_session_identifier_are_checked(self):
        refresh = create_refresh_token(**TOKEN_ARGS, token_id='session-one')
        access = create_access_token(**TOKEN_ARGS)
        for decoder, token in ((decode_refresh_token, access), (decode_access_token, refresh)):
            with self.subTest(decoder=decoder.__name__), self.assertRaises(ApiError) as error:
                decoder(token, SECRET)
            self.assertEqual(error.exception.status_code, 401)
        payload = jwt.decode(refresh, SECRET, algorithms=['HS256'])
        for field, value in [('token_type', None), ('token_type', 'reset'),
                             ('token_id', None), ('token_id', ''), ('token_id', 123)]:
            malformed = dict(payload)
            if value is None:
                del malformed[field]
            else:
                malformed[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ApiError) as error:
                decode_refresh_token(jwt.encode(malformed, SECRET, algorithm='HS256'), SECRET)
            self.assertEqual(error.exception.status_code, 401)

    def test_access_and_refresh_expire_at_the_exp_boundary(self):
        pairs = [(decode_access_token, create_access_token(**TOKEN_ARGS)),
                 (decode_refresh_token, create_refresh_token(**TOKEN_ARGS, token_id='boundary'))]
        for decoder, token in pairs:
            expiry = jwt.decode(token, SECRET, algorithms=['HS256'])['exp']
            with self.subTest(decoder=decoder.__name__), patch('jwt.api_jwt.datetime') as clock:
                clock.now.return_value = datetime.fromtimestamp(expiry - 1, timezone.utc)
                self.assertEqual(decoder(token, SECRET)['user_id'], 7)
                for now in (expiry, expiry + 1):
                    clock.now.return_value = datetime.fromtimestamp(now, timezone.utc)
                    with self.assertRaises(ApiError) as error:
                        decoder(token, SECRET)
                    self.assertEqual(error.exception.status_code, 401)
                    self.assertEqual(error.exception.message, '登录已过期，请重新登录')

    def test_bad_signature_and_malformed_token_are_rejected(self):
        wrong_secret = create_refresh_token(**{**TOKEN_ARGS, 'secret': 'other-fixture'}, token_id='bad')
        for token in (wrong_secret, 'not-a-jwt', ''):
            with self.subTest(token_kind='invalid'), self.assertRaises(ApiError) as error:
                decode_refresh_token(token, SECRET)
            self.assertEqual(error.exception.status_code, 401)


class RefreshHTTPTests(AsyncHTTPTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        binary = shutil.which('redis-server')
        if not binary:
            raise RuntimeError('redis-server is required for refresh HTTP regression tests')
        cls.tmp = tempfile.TemporaryDirectory(prefix='bf-refresh-test-')
        cls.addClassCleanup(cls.tmp.cleanup)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            cls.redis_port = sock.getsockname()[1]
        cls.redis_process = subprocess.Popen(
            [binary, '--bind', '127.0.0.1', '--port', str(cls.redis_port), '--save', '',
             '--appendonly', 'no', '--dir', cls.tmp.name],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        cls.addClassCleanup(cls.stop_redis)
        for _ in range(100):
            if cls.redis_process.poll() is not None:
                raise RuntimeError('isolated Redis exited during startup')
            try:
                with socket.create_connection(('127.0.0.1', cls.redis_port), timeout=.1):
                    break
            except OSError:
                time.sleep(.02)
        else:
            raise RuntimeError('isolated Redis did not start')

    @classmethod
    def stop_redis(cls):
        cls.redis_process.terminate()
        try:
            cls.redis_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            cls.redis_process.kill()
            cls.redis_process.wait(timeout=5)

    def get_app(self):
        self.settings = replace(load_settings(), redis_host='127.0.0.1', redis_port=self.redis_port,
                                redis_db=0, jwt_secret=SECRET, jwt_expire_seconds=300,
                                jwt_refresh_expire_seconds=600)
        return Application(build_routes(), app_settings=self.settings)

    def setUp(self):
        super().setUp()
        self.user = dict(id=7, username='refresh_fixture', nickname='续期测试', role='user',
                         status=1, password_hash='fixture-only', balance_cents=0, points=0)
        self.patches = [
            patch('repositories.user_repository.get_user_by_id',
                  AsyncMock(side_effect=lambda _, uid: dict(self.user) if self.user and uid == 7 else None)),
            patch('repositories.database.get_pool',
                  AsyncMock(side_effect=AssertionError('refresh tests must not connect to MySQL'))),
        ]
        for item in self.patches:
            item.start()
        self.io_loop.run_sync(lambda: redis_service.get_redis_client(self.settings).flushdb())

    def tearDown(self):
        try:
            self.io_loop.run_sync(redis_service.close_redis_clients)
        finally:
            for item in reversed(self.patches):
                item.stop()
            super().tearDown()

    async def request(self, path='/api/auth/refresh', body=None, *, token=None, status=200, method='POST'):
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        response = await self.http_client.fetch(
            self.get_url(path), method=method, headers=headers,
            body=None if method == 'GET' else json.dumps(body if body is not None else {}),
            raise_error=False,
        )
        self.assertEqual(response.code, status, response.body)
        payload = json.loads(response.body)
        self.assertEqual(payload['code'], 0 if status == 200 else status)
        if status != 200:
            self.assertIsNone(payload['data'])
        return payload['data'] if status == 200 else payload

    def refresh_key(self, token):
        payload = jwt.decode(token, SECRET, algorithms=['HS256'], options={'verify_exp': False})
        return auth_service._refresh_key(payload['user_id'], payload['token_id'])

    @gen_test
    async def test_refresh_returns_current_user_and_usable_rotated_tokens(self):
        old_access, old_refresh = await auth_service.issue_tokens(self.settings, self.user)
        self.user.update(nickname='最新资料', role='frontdesk')
        data = await self.request(body={'refresh_token': old_refresh})
        self.assertEqual(data['token'], data['access_token'])
        self.assertNotEqual(data['access_token'], old_access)
        self.assertNotEqual(data['refresh_token'], old_refresh)
        self.assertEqual(data['user']['nickname'], '最新资料')
        self.assertEqual(decode_access_token(data['access_token'], SECRET)['role'], 'frontdesk')
        self.assertEqual(decode_refresh_token(data['refresh_token'], SECRET)['role'], 'frontdesk')
        profile = await self.request('/api/auth/profile', token=data['access_token'], method='GET')
        self.assertEqual(profile['id'], 7)
        client = redis_service.get_redis_client(self.settings)
        self.assertFalse(await client.exists(self.refresh_key(old_refresh)))
        self.assertGreater(await client.ttl(self.refresh_key(data['refresh_token'])), 0)

    @gen_test
    async def test_expired_access_token_does_not_prevent_refresh(self):
        expired_access, valid_refresh = await auth_service.issue_tokens(
            replace(self.settings, jwt_expire_seconds=-60), self.user)
        await self.request('/api/auth/profile', token=expired_access, method='GET', status=401)
        data = await self.request(body={'refresh_token': valid_refresh}, token=expired_access)
        profile = await self.request('/api/auth/profile', token=data['access_token'], method='GET')
        self.assertEqual(profile['id'], 7)

    @gen_test
    async def test_access_and_refresh_cannot_be_used_in_place_of_each_other(self):
        access, refresh = await auth_service.issue_tokens(self.settings, self.user)
        await self.request(body={'refresh_token': access}, status=401)
        await self.request('/api/auth/profile', token=refresh, method='GET', status=401)
        self.assertTrue(await redis_service.get_redis_client(self.settings).exists(self.refresh_key(refresh)))
        self.assertEqual((await self.request(body={'refresh_token': refresh}))['user']['id'], 7)

    @gen_test
    async def test_missing_invalid_type_or_signature_never_issues_a_session(self):
        refresh = create_refresh_token(**TOKEN_ARGS, token_id='invalid-claims')
        payload = jwt.decode(refresh, SECRET, algorithms=['HS256'])
        bodies = [{}, {'refresh_token': ''}, {'refresh_token': 'not-a-jwt'},
                  {'refresh_token': jwt.encode(payload, 'wrong-secret', algorithm='HS256')}]
        for field, value in [('token_type', None), ('token_type', 'reset'), ('token_id', None), ('token_id', '')]:
            altered = dict(payload)
            if value is None:
                del altered[field]
            else:
                altered[field] = value
            bodies.append({'refresh_token': jwt.encode(altered, SECRET, algorithm='HS256')})
        for body in bodies:
            await self.request(body=body, status=401)
        self.assertEqual(await redis_service.get_redis_client(self.settings).dbsize(), 0)

    @gen_test
    async def test_expired_jwt_is_rejected_even_if_redis_session_is_alive(self):
        expired = create_refresh_token(**{**TOKEN_ARGS, 'expire_seconds': -60}, token_id='expired')
        key = self.refresh_key(expired)
        client = redis_service.get_redis_client(self.settings)
        await client.set(key, '1', ex=60)
        response = await self.request(body={'refresh_token': expired}, status=401)
        self.assertEqual(response['message'], '登录已过期，请重新登录')
        self.assertEqual(await client.dbsize(), 1)
        self.assertTrue(await client.exists(key))

    @gen_test
    async def test_expired_or_revoked_redis_session_is_rejected(self):
        client = redis_service.get_redis_client(self.settings)
        for revoked in (False, True):
            _, refresh = await auth_service.issue_tokens(self.settings, self.user)
            key = self.refresh_key(refresh)
            if revoked:
                await auth_service.revoke_user_refresh_tokens(self.settings, 7)
            else:
                await client.pexpireat(key, int(time.time() * 1000) - 1)
            self.assertFalse(await client.exists(key))
            response = await self.request(body={'refresh_token': refresh}, status=401)
            self.assertEqual(response['message'], '登录状态已失效，请重新登录')
            self.assertEqual(await client.dbsize(), 0)

    @gen_test
    async def test_rotated_token_can_refresh_again_and_old_token_cannot_replay(self):
        _, refresh = await auth_service.issue_tokens(self.settings, self.user)
        first = await self.request(body={'refresh_token': refresh})
        await self.request(body={'refresh_token': refresh}, status=401)
        second = await self.request(body={'refresh_token': first['refresh_token']})
        self.assertNotEqual(first['refresh_token'], second['refresh_token'])
        await self.request('/api/auth/logout', body={'refresh_token': second['refresh_token']})
        await self.request(body={'refresh_token': second['refresh_token']}, status=401)
        self.assertEqual(await redis_service.get_redis_client(self.settings).dbsize(), 0)

    @gen_test
    async def test_disabled_or_missing_user_cannot_refresh(self):
        _, refresh = await auth_service.issue_tokens(self.settings, self.user)
        self.user['status'] = 0
        await self.request(body={'refresh_token': refresh}, status=403)
        self.user = None
        await self.request(body={'refresh_token': refresh}, status=401)
        self.assertEqual(await redis_service.get_redis_client(self.settings).dbsize(), 1)

    @gen_test
    async def test_json_body_must_be_an_object(self):
        for body in ([], 'refresh-token', 123):
            await self.request(body=body, status=400)


if __name__ == '__main__':
    unittest.main()
