"""Real HTTP + an owned temporary Redis. User/order reads are controlled fixtures."""
import asyncio
from dataclasses import replace
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, patch
from urllib.parse import urlsplit, parse_qs

from tornado.testing import AsyncHTTPTestCase, gen_test
from tornado.web import Application
from config.settings import load_settings
from routes import build_routes
from services import auth_service, mobile_handoff_service as service, redis_service
from utils.tokens import create_access_token, create_refresh_token, decode_access_token, decode_refresh_token
from utils.response import ApiError


class TokenTypeTests(unittest.TestCase):
    def test_access_and_refresh_are_separate_and_sessions_unique(self):
        args = dict(user_id=1, username='test', role='user', secret='test-secret', expire_seconds=120)
        access = create_access_token(**args)
        self.assertNotEqual(access, create_access_token(**args))
        refresh = create_refresh_token(**args, token_id='one-phone')
        self.assertEqual(decode_access_token(access, 'test-secret')['user_id'], 1)
        self.assertEqual(decode_refresh_token(refresh, 'test-secret')['token_id'], 'one-phone')
        with self.assertRaises(ApiError): decode_access_token(refresh, 'test-secret')
        with self.assertRaises(ApiError): decode_refresh_token(access, 'test-secret')


class MobileHandoffTests(AsyncHTTPTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        binary = shutil.which('redis-server')
        if not binary: raise RuntimeError('redis-server is required for the handoff integration tests')
        cls.tmp = tempfile.TemporaryDirectory(prefix='bf-handoff-test-')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0)); cls.redis_port = sock.getsockname()[1]
        cls.redis_process = subprocess.Popen([binary, '--bind', '127.0.0.1', '--port', str(cls.redis_port),
            '--save', '', '--appendonly', 'no', '--dir', cls.tmp.name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                with socket.create_connection(('127.0.0.1', cls.redis_port), timeout=.1): break
            except OSError: time.sleep(.02)
        else: raise RuntimeError('isolated Redis did not start')

    @classmethod
    def tearDownClass(cls):
        cls.redis_process.terminate(); cls.redis_process.wait(timeout=5); cls.tmp.cleanup()
        super().tearDownClass()

    def get_app(self):
        self.settings = replace(load_settings(), redis_port=self.redis_port, redis_db=0,
                                jwt_secret='handoff-fixture-only', mobile_web_origin='https://club.example')
        return Application(build_routes(), app_settings=self.settings)

    def setUp(self):
        super().setUp()
        self.users = {i: dict(id=i, username=f'customer{i}', nickname=f'测试客户{i}', status=1, role=role,
                             password_hash='fixture-password', balance_cents=10000, member_level='normal', points=0)
                      for i, role in ((1,'user'),(2,'user'),(3,'admin'),(4,'frontdesk'),(5,'maintenance'))}
        self.order = dict(id=7, user_id=1, status='paid', pickup_status='ready')
        self.patches = [patch('repositories.user_repository.get_user_by_id', AsyncMock(side_effect=lambda _, uid: dict(self.users[uid]) if uid in self.users else None)),
                        patch('repositories.shop_repository.get_order', AsyncMock(side_effect=lambda _, oid: dict(self.order) if oid == 7 else None))]
        for p in self.patches: p.start()
        self.io_loop.run_sync(lambda: redis_service.get_redis_client(self.settings).flushdb())
        self.desktop = self.token(1)

    def tearDown(self):
        for p in reversed(self.patches): p.stop()
        self.io_loop.run_sync(redis_service.close_redis_clients)
        super().tearDown()

    def token(self, uid):
        user = self.users[uid]
        return create_access_token(user_id=uid, username=user['username'], role=user['role'],
                                   secret=self.settings.jwt_secret, expire_seconds=300)

    async def request(self, suffix='', body=None, token=None, code=200, method='POST'):
        response = await self.http_client.fetch(self.get_url('/api/auth/mobile-handoffs' + suffix), method=method,
            headers={'Content-Type': 'application/json', **({'Authorization': 'Bearer '+token} if token else {})},
            body=None if method=='GET' else json.dumps(body or {}), raise_error=False)
        self.assertEqual(response.code, code, response.body)
        self.assertEqual(response.headers.get('Cache-Control'), 'no-store')
        data = json.loads(response.body)
        return data['data'] if code == 200 else data

    async def create(self):
        return await self.request(body={'order_id':7}, token=self.desktop)

    async def pair(self):
        grant = await self.create()
        ticket = parse_qs(urlsplit(grant['mobile_url']).fragment)['ticket'][0]
        phone = dict(ticket=ticket, device_secret=secrets.token_urlsafe(32))
        claimed = await self.request('/'+grant['id']+'/claim', phone)
        return grant, phone, claimed

    async def approve(self, grant, claimed):
        return await self.request('/'+grant['id']+'/decision', {'decision':'approve','pairing_code':claimed['pairing_code']}, self.desktop)

    async def result(self, grant, phone):
        for _ in range(10):
            response = await self.request('/'+grant['id']+'/exchange', phone)
            if 'login' in response: return response
            await asyncio.sleep(.01)
        self.fail('no login result')

    @gen_test
    async def test_roles_ownership_order_states_and_input(self):
        await self.request(body={'order_id':7}, code=401)
        for uid in (3,4,5): await self.request(body={'order_id':7}, token=self.token(uid), code=403)
        await self.request(body={'order_id':7}, token=self.token(2), code=404)
        for value in (None, True, '7', 0, -1):
            await self.request(body={'order_id':value}, token=self.desktop, code=400)
        for status in ('pending','refund_requested','canceled','completed'):
            self.order['status']=status
            await self.request(body={'order_id':7}, token=self.desktop, code=409)

    @gen_test
    async def test_qr_contains_no_account_token_and_claim_keeps_secrets_private(self):
        grant, phone, claimed = await self.pair()
        self.assertNotIn(self.desktop, json.dumps(grant))
        self.assertTrue(grant['mobile_url'].startswith('https://club.example/mobile-handoff/'))
        self.assertNotIn('?', grant['mobile_url'])
        self.assertRegex(claimed['pairing_code'], r'^\d{6}$')
        status = await self.request('/'+grant['id'], token=self.desktop, method='GET')
        for forbidden in ('login','ticket','device_secret','issuer_digest','password_digest'):
            self.assertNotIn(forbidden, status)
        _, raw, _ = await service.read(self.settings, grant['id'])
        self.assertNotIn(phone['ticket'], raw); self.assertNotIn(phone['device_secret'], raw)

    @gen_test
    async def test_only_issuer_session_can_approve_and_code_must_match(self):
        grant = await self.create()
        await self.request('/'+grant['id']+'/decision', {'decision':'approve','pairing_code':'000000'}, self.desktop, code=409)
        grant, phone, claimed = await self.pair()
        for token in (self.token(1), self.token(2)):
            await self.request('/'+grant['id'], token=token, method='GET', code=403)
            await self.request('/'+grant['id']+'/decision', {'decision':'approve','pairing_code':claimed['pairing_code']}, token, code=403)
        await self.request('/'+grant['id']+'/decision', {'decision':'approve','pairing_code':'wrong'}, self.desktop, code=409)
        waiting = await self.request('/'+grant['id']+'/exchange', phone)
        self.assertNotIn('login', waiting)

    @gen_test
    async def test_competing_phones_bind_exactly_one_device(self):
        grant = await self.create(); ticket=parse_qs(urlsplit(grant['mobile_url']).fragment)['ticket'][0]
        devices=[{'ticket':ticket,'device_secret':secrets.token_urlsafe(32)} for _ in range(12)]
        outcomes=await asyncio.gather(*(service.claim(self.settings,grant['id'],body) for body in devices),return_exceptions=True)
        self.assertEqual(sum(isinstance(result,dict) for result in outcomes),1)
        winner=next(i for i,result in enumerate(outcomes) if isinstance(result,dict))
        for i,body in enumerate(devices):
            if i!=winner: await self.request('/'+grant['id']+'/exchange',body,code=403)
        await self.request('/'+grant['id']+'/claim',devices[winner])

    @gen_test
    async def test_bad_ticket_cannot_claim(self):
        grant=await self.create()
        await self.request('/'+grant['id']+'/claim',{'ticket':secrets.token_urlsafe(32),'device_secret':secrets.token_urlsafe(32)},code=403)
        await self.request('/'+grant['id']+'/claim',{'ticket':'x','device_secret':'x'},code=400)

    @gen_test
    async def test_deny_cancel_and_expiry(self):
        for decision in ('deny','cancel'):
            grant,phone,claimed=await self.pair()
            await self.request('/'+grant['id']+'/decision',{'decision':decision},self.desktop)
            await self.request('/'+grant['id']+'/exchange',phone,code=410)
        grant,phone,claimed=await self.pair()
        await redis_service.get_redis_client(self.settings).pexpire(service.PREFIX+grant['id'], 10)
        await asyncio.sleep(.03)
        await self.request('/'+grant['id']+'/exchange',phone,code=410)

    @gen_test
    async def test_approval_racing_cancellation_cannot_restore_denied_request(self):
        grant,phone,claimed=await self.pair()
        await asyncio.gather(
            service.decide(self.settings,self.users[1],self.desktop,grant['id'],{'decision':'approve','pairing_code':claimed['pairing_code']}),
            service.decide(self.settings,self.users[1],self.desktop,grant['id'],{'decision':'cancel'}),
            return_exceptions=True)
        state=await service.status(self.settings,self.users[1],self.desktop,grant['id'])
        self.assertEqual(state['status'],'denied')
        await self.request('/'+grant['id']+'/exchange',phone,code=410)

    @gen_test
    async def test_phone_response_recovery_closes_after_receipt_ttl(self):
        grant,phone,claimed=await self.pair();await self.approve(grant,claimed)
        await self.result(grant,phone)
        await redis_service.get_redis_client(self.settings).pexpire(service.PREFIX+grant['id'],10)
        await asyncio.sleep(.03)
        await self.request('/'+grant['id']+'/exchange',phone,code=410)

    @gen_test
    async def test_concurrent_exchange_and_lost_response_issue_one_session(self):
        grant,phone,claimed=await self.pair(); await self.approve(grant,claimed)
        with patch.object(auth_service,'issue_tokens',wraps=auth_service.issue_tokens) as issue:
            results=await asyncio.gather(*(service.exchange(self.settings,grant['id'],phone) for _ in range(20)))
            issued=[r['login'] for r in results if 'login' in r]
            self.assertGreater(len(issued),0); self.assertEqual(issue.call_count,1)
            retry=await self.result(grant,phone)
            self.assertEqual(retry['login'],issued[0]); self.assertEqual(issue.call_count,1)
        self.assertNotEqual(retry['login']['access_token'],self.desktop)
        ttl=await redis_service.ttl(self.settings,service.PREFIX+grant['id'])
        self.assertGreater(ttl,0); self.assertLessEqual(ttl,30)
        await self.request('/'+grant['id']+'/exchange',{'device_secret':secrets.token_urlsafe(32)},code=403)
        state=await self.request('/'+grant['id'],token=self.desktop,method='GET')
        self.assertNotIn('login',state)

    @gen_test
    async def test_live_account_and_order_rechecks(self):
        mutations=[('role','admin'),('status',0),('password_hash','changed')]
        for field,value in mutations:
            grant,phone,claimed=await self.pair(); await self.approve(grant,claimed)
            original=self.users[1][field];self.users[1][field]=value
            await self.request('/'+grant['id']+'/exchange',phone,code=409 if field=='password_hash' else 403)
            self.users[1][field]=original
        grant,phone,claimed=await self.pair();self.order['status']='refund_requested'
        await self.request('/'+grant['id']+'/decision',{'decision':'approve','pairing_code':claimed['pairing_code']},self.desktop,code=409)
        self.order['status']='paid';await self.approve(grant,claimed);self.order['status']='completed'
        await self.request('/'+grant['id']+'/exchange',phone,code=409)

    @gen_test
    async def test_mobile_refresh_and_logout_leave_desktop_session(self):
        desktop_access,desktop_refresh=await auth_service.issue_tokens(self.settings,self.users[1])
        grant,phone,claimed=await self.pair();await self.approve(grant,claimed)
        mobile=(await self.result(grant,phone))['login']
        refreshed=await auth_service.refresh_login(self.settings,{'refresh_token':mobile['refresh_token']})
        await auth_service.logout(self.settings,{'refresh_token':refreshed['refresh_token']})
        with self.assertRaises(ApiError): await auth_service.refresh_login(self.settings,{'refresh_token':refreshed['refresh_token']})
        retained=await auth_service.refresh_login(self.settings,{'refresh_token':desktop_refresh})
        self.assertEqual(retained['user']['id'],1)
        response=await self.http_client.fetch(self.get_url('/api/auth/profile'),headers={'Authorization':'Bearer '+mobile['access_token']})
        self.assertEqual(json.loads(response.body)['data']['id'],1)

    @gen_test
    async def test_issue_failure_is_not_retried_as_second_session(self):
        grant,phone,claimed=await self.pair();await self.approve(grant,claimed)
        with patch.object(auth_service,'issue_tokens',AsyncMock(side_effect=RuntimeError('injected'))):
            with self.assertRaises(RuntimeError): await service.exchange(self.settings,grant['id'],phone)
        await self.request('/'+grant['id']+'/exchange',phone,code=410)

    @gen_test
    async def test_config_and_limits(self):
        for origin in ('','http://localhost:5188','http://127.0.0.1:5188','https://host.example/path','https://name:pass@host.example','https://host.example#x'):
            with self.assertRaises(ApiError): service.web_origin(replace(self.settings,mobile_web_origin=origin))
        with self.assertRaises(ApiError): service.web_origin(replace(self.settings,app_env='production',mobile_web_origin='http://192.168.1.8:5188'))
        self.assertEqual(service.web_origin(replace(self.settings,app_env='dev',mobile_web_origin='http://192.168.1.8:5188')),'http://192.168.1.8:5188')
        for _ in range(10): await self.create()
        await self.request(body={'order_id':7},token=self.desktop,code=429)
