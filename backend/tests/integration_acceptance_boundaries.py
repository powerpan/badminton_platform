"""Remaining acceptance boundaries using real MySQL transactions and JWT HTTP.

Creates and removes only its own disposable database. No cleanup worker is
started: expiry must be enforced by requests and by an explicit later sweep.
"""
import asyncio
from dataclasses import replace
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import secrets
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from dotenv import load_dotenv
load_dotenv(ROOT / 'backend/.env')
import aiomysql
from tornado.httpclient import AsyncHTTPClient, HTTPRequest
from tornado.httpserver import HTTPServer
from tornado.netutil import bind_sockets
from tornado.web import Application
from config.settings import load_settings
from repositories import database, staff_booking_repository as staff_repo
from repositories.database import execute, fetch_all, fetch_one, close_pool
from routes import build_routes
from services import staff_booking_service as staff, reservation_service, payment_service
from utils.response import ApiError
from utils.tokens import create_access_token


async def run():
    settings = replace(load_settings(), mysql_database='badminton_demo_acceptance_' + secrets.token_hex(8),
                       jwt_secret=secrets.token_urlsafe(32))
    name = settings.mysql_database
    assert re.fullmatch(r'badminton_demo_acceptance_[0-9a-f]{16}', name)
    con = await aiomysql.connect(host=settings.mysql_host, port=settings.mysql_port,
        user=settings.mysql_user, password=settings.mysql_password, autocommit=True)
    created, server = False, None
    client = AsyncHTTPClient(force_instance=True)
    checks, tables = [], []
    actors = {role: {'id': uid, 'username': 'acceptance_' + role, 'role': role}
              for uid, role in enumerate(('admin', 'user', 'frontdesk', 'maintenance'), 1)}
    other_desk = {'id': 5, 'username': 'acceptance_desk_two', 'role': 'frontdesk'}
    actors['other_user'] = {'id': 6, 'username': 'acceptance_other_user', 'role': 'user'}

    async def clock(value):
        await close_pool()
        instant = datetime.fromisoformat('2026-10-01T' + value)
        database._pool = await aiomysql.create_pool(host=settings.mysql_host, port=settings.mysql_port,
            user=settings.mysql_user, password=settings.mysql_password, db=name, minsize=1, maxsize=10,
            autocommit=True, init_command=f'SET timestamp={int(instant.timestamp())}')

    async def config(key, value):
        await execute(settings, 'INSERT INTO config(config_key,config_value) VALUES (%s,%s) '
                      'ON DUPLICATE KEY UPDATE config_value=VALUES(config_value)', (key, str(value)))

    def body(court, start='14:00', end='15:00', amount=12000):
        return {'court_id': court, 'reserve_date': '2026-10-01', 'start_time': start, 'end_time': end,
                'expected_amount_cents': amount, 'request_key': secrets.token_hex(12), 'guest_name': '隔离验收散客'}

    async def create(payload, actor=None, parent=None):
        return await staff.create(settings, actor or actors['frontdesk'], payload, parent)

    async def act(order, action='mock_confirm'):
        return await staff.action(settings, actors['frontdesk'], order['id'], action,
                                  {'request_key': secrets.token_hex(12)})

    async def reject(call, code):
        try:
            await call
        except ApiError as exc:
            assert exc.status_code == code, (code, exc.status_code, exc.message)
        else:
            raise AssertionError('Expected rejection')

    async def fingerprint():
        rows = {}
        for table in tables:
            values = await fetch_all(settings, f'SELECT * FROM `{table}`')
            rows[table] = sorted(json.dumps(row, sort_keys=True, default=str) for row in values)
        return hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()

    try:
        async with con.cursor() as cursor:
            await cursor.execute(f'CREATE DATABASE `{name}` CHARACTER SET utf8mb4')
            created = True
            await cursor.execute(f'USE `{name}`')
            for statement in re.findall(r'CREATE TABLE IF NOT EXISTS \w+ \(.*?\) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;',
                                        (ROOT / 'sql/init.sql').read_text(), re.S):
                tables.append(re.search(r'EXISTS (\w+)', statement).group(1))
                await cursor.execute(statement)
        await clock('14:10:00')
        for actor in (*actors.values(), other_desk):
            await execute(settings, 'INSERT INTO user(id,username,nickname,password_hash,role) VALUES (%s,%s,%s,%s,%s)',
                          (actor['id'], actor['username'], '隔离验收账号', 'test-only-no-login', actor['role']))
            await execute(settings, 'INSERT INTO member_account(user_id,balance_cents,points) VALUES (%s,%s,400)',
                          (actor['id'], 100000 if actor['role'] in ('admin', 'user') else 0))
        for cid in range(1, 22):
            await execute(settings, 'INSERT INTO court(id,court_no,court_name,price_per_hour_cents) VALUES (%s,%s,%s,%s)',
                          (cid, f'AC{cid}', f'隔离验收场 {cid}', 10000 if cid == 2 else 12000))

        tokens = {role: create_access_token(user_id=actor['id'], username=actor['username'], role=actor['role'],
                  secret=settings.jwt_secret, expire_seconds=3600) for role, actor in actors.items()}
        server = HTTPServer(Application(build_routes(), app_settings=settings, log_function=lambda _: None))
        sockets = bind_sockets(0, '127.0.0.1')
        server.add_sockets(sockets)
        origin = f'http://127.0.0.1:{sockets[0].getsockname()[1]}'

        async def request(path, method='GET', role=None, payload=None):
            headers = {'Content-Type': 'application/json'}
            if role:
                headers['Authorization'] = 'Bearer ' + tokens[role]
            response = await client.fetch(HTTPRequest(origin + path, method=method, headers=headers,
                body=None if method in ('GET', 'DELETE') else json.dumps(payload or {})), raise_error=False)
            return response.code, json.loads(response.body)

        before = await fingerprint()
        refusals = 0
        for role in ('frontdesk', 'maintenance', 'user'):
            for pattern, handler in build_routes():
                if not pattern.startswith('/api/admin/'):
                    continue
                path = pattern.replace('([0-9]+)', '1').replace('([^/]+)', '1').replace('([A-Za-z0-9_]+)', 'test_key')
                assert '(' not in path, pattern
                for method in ('get', 'post', 'put', 'delete'):
                    if method not in handler.__dict__:
                        continue
                    status, _ = await request(path, method.upper(), role)
                    assert status == 403, (role, path, method, status)
                    refusals += 1
        for role in ('admin', 'frontdesk', 'maintenance'):
            status, _ = await request('/api/auth/register', 'POST', payload={'role': role})
            assert status == 400
        assert await fingerprint() == before
        checks.append({'cases': ['TC-03', 'TC-04'], 'result': 'all admin endpoints reject real non-admin JWTs; privileged registration rejected; all table rows unchanged', 'denied_http_requests': refusals})

        assert (await request('/api/admin/users', role='admin'))[0] == 200
        await execute(settings, "UPDATE user SET role='frontdesk' WHERE id=1")
        assert (await request('/api/admin/users', role='admin'))[0] == 403
        status, profile = await request('/api/auth/profile', role='admin')
        assert status == 200 and profile['data']['role'] == 'frontdesk'
        await execute(settings, 'UPDATE user SET status=0 WHERE id=1')
        assert (await request('/api/auth/profile', role='admin'))[0] == 403
        await execute(settings, "UPDATE user SET status=1,role='admin' WHERE id=1")
        assert (await request('/api/admin/users', role='admin'))[0] == 200
        checks.append({'cases': ['TC-05'], 'result': 'same real JWT immediately follows database role, disabled state and restored permissions'})

        await config('slot_interval_minutes', 30)
        for cid, end, amount in ((1, '14:30', 6000), (2, '14:30', 5000), (3, '15:00', 12000)):
            quote = await staff.quote(settings, actors['frontdesk'], body(cid, end=end, amount=amount))
            order = await create(body(cid, end=end, amount=amount))
            assert quote['payable_amount_cents'] == order['payment']['amount_cents'] == amount
            assert order['points_awarded'] == 0 and order['user_id'] is None
        await execute(settings, "INSERT INTO court_block(court_id,reserve_date,start_time,end_time,reason,status,created_by,block_type) "
                      "VALUES (4,'2026-10-01','14:30','15:00','隔离维修','active',1,'maintenance')")
        await reject(create(body(4)), 409)
        assert (await create(body(4, end='14:30', amount=6000)))['payment']['amount_cents'] == 6000
        checks.append({'cases': ['TC-07'], 'result': '30-minute and two-segment quotes equal full segment totals at two court prices; cannot cross blocked segment; adjacent segment remains bookable'})

        await config('daily_reservation_limit', 1)
        for cid in (5, 6, 7):
            assert (await create(body(cid, end='14:30', amount=6000)))['user_id'] is None
        count = len(await fetch_all(settings, 'SELECT id FROM reservation'))
        for start, end, code in (('13:30', '14:00', 409), ('15:00', '15:30', 409), ('08:30', '09:00', 400),
                                  ('14:10', '15:00', 400), ('14:00', '17:00', 400), ('14:00', '22:00', 400)):
            await reject(create(body(8, start=start, end=end)), code)
        assert len(await fetch_all(settings, 'SELECT id FROM reservation')) == count
        checks.append({'cases': ['TC-08'], 'result': 'past, future, outside hours, unaligned and overlong walk-ins rejected; three guests accepted despite personal daily limit one'})

        await config('slot_interval_minutes', 60)
        root = await create(body(9))
        await act(root)
        gate = asyncio.Event()

        async def contender(operation):
            await gate.wait()
            return await operation()

        target = {**body(9, start='15:00', end='16:00'), 'pay_method': 'mock_alipay'}
        tasks = [asyncio.create_task(contender(operation)) for operation in (
            lambda: reservation_service.create_reservation(settings, current_user=actors['user'], body=target),
            lambda: create(body(9, end='16:00'), parent=root['id']),
            lambda: create(body(9, end='16:00'), other_desk, root['id']))]
        gate.set()
        outcomes = await asyncio.gather(*tasks, return_exceptions=True)
        assert sum(isinstance(value, dict) for value in outcomes) == 1, outcomes
        assert all(isinstance(value, dict) or isinstance(value, ApiError) and value.status_code == 409 for value in outcomes), outcomes
        active = await fetch_all(settings, "SELECT id FROM reservation WHERE court_id=9 AND start_time='15:00' AND status='pending'")
        assert len(active) == 1
        assert (await staff_repo.get_order(settings, root['id']))['end_time'] == '15:00'
        checks.append({'cases': ['TC-09', 'TC-13'], 'result': 'one online customer and two frontdesks race for adjacent segment: exactly one hold; paid original end time remains unchanged'})

        parent = await create(body(14))
        await act(parent)
        block_id = await execute(settings, "INSERT INTO court_block(court_id,reserve_date,start_time,end_time,reason,status,created_by,block_type) "
                                 "VALUES (14,'2026-10-01','15:00','16:00','隔离续场维修','active',1,'maintenance')")
        extension_body = body(14, end='16:00')
        await reject(create(extension_body, parent=parent['id']), 409)
        await execute(settings, "UPDATE court_block SET status='released',released_at=NOW() WHERE id=%s", (block_id,))
        first, repeated = await asyncio.gather(create(extension_body, parent=parent['id']),
                                               create(extension_body, parent=parent['id']))
        assert first['id'] == repeated['id'] and first['parent_reservation_id'] == parent['id']
        await act(first, 'mock_fail')
        assert (await staff_repo.get_order(settings, parent['id']))['end_time'] == '15:00'
        assert (await staff_repo.get_order(settings, first['id']))['payment']['status'] == 'pending'
        await act(first)
        await act(first)
        totals = await fetch_one(settings, "SELECT COUNT(*) AS n,SUM(p.amount_cents) AS amount FROM payment_order p "
            "JOIN reservation_order o ON o.id=p.reservation_order_id WHERE o.reservation_id IN (%s,%s) AND p.status='succeeded'", (parent['id'], first['id']))
        assert totals['n'] == 2 and int(totals['amount']) == 24000
        checks.append({'cases': ['TC-12', 'TC-13'], 'result': 'maintenance blocks extension; repeated identical creation returns one child; failed/unpaid child keeps parent deadline; repeated collection charges child only once'})

        await clock('14:55:00')
        timely = await create(body(10, end='16:00', amount=24000))
        late = await create(body(11, end='16:00', amount=24000))
        lookup_late = await create(body(12))
        race_late = await create(body(13))
        assert all(order['payment']['expires_at'].endswith('15:00:00+08:00') for order in (timely, late, lookup_late, race_late))
        await clock('14:59:59')
        assert (await act(timely))['payment']['status'] == 'succeeded'
        await clock('15:00:00')
        await reject(act(late), 409)
        assert (await staff_repo.get_order(settings, lookup_late['id']))['payment']['status'] == 'expired'
        outcomes = await asyncio.gather(act(race_late), staff_repo.expire_pending(settings), return_exceptions=True)
        assert isinstance(outcomes[0], ApiError) and outcomes[0].status_code == 409
        assert isinstance(outcomes[1], int)
        await staff_repo.expire_pending(settings)
        assert await staff_repo.expire_pending(settings) == 0
        for order in (late, lookup_late, race_late):
            state = await staff_repo.get_order(settings, order['id'])
            assert state['status'] == state['order_status'] == state['payment']['status'] == 'expired'
            audit = await fetch_one(settings, "SELECT COUNT(*) AS n FROM operation_log WHERE module='payment' AND action='expire' AND target_id=%s", (order['payment']['id'],))
            assert audit['n'] == 1
        assert (await staff_repo.get_order(settings, timely['id']))['status'] == 'confirmed'
        assert (await create(body(11, start='15:00', end='16:00')))['id'] != late['id']
        checks.append({'cases': ['TC-10', 'TC-11'], 'result': 'two-hour order payable at 14:59:59, rejected at first segment end 15:00; without worker query/payment expire once; concurrent sweep/payment and repeated cleanup leave no duplicate effect; court reusable'})

        await config('daily_reservation_limit', 10)
        await execute(settings, "UPDATE member_account SET member_level='gold',expires_at='2026-09-30' WHERE user_id=2")
        before_account = await fetch_one(settings, 'SELECT balance_cents,points FROM member_account WHERE user_id=2')
        for cid, method in ((20, 'balance'), (21, 'mock_alipay')):
            payload = {**body(cid, start='16:00', end='17:00'), 'reserve_date': '2026-10-02', 'pay_method': method}
            order = await reservation_service.create_reservation(settings, current_user=actors['user'], body=payload)
            assert order['payable_amount_cents'] == 12000 and order['discount_rate'] == 100 and order['points_awarded'] == 120
            await payment_service.act(settings, actors['user'], order['payment_id'], 'balance_pay' if method == 'balance' else 'mock_confirm', {'request_key': secrets.token_hex(12)})
        after_account = await fetch_one(settings, 'SELECT balance_cents,points FROM member_account WHERE user_id=2')
        assert after_account == {'balance_cents': before_account['balance_cents'] - 12000, 'points': before_account['points'] + 240}
        checks.append({'cases': ['TC-16'], 'result': 'expired gold member pays original price and receives equal points with both channels; only balance channel deducts wallet'})

        await execute(settings, "INSERT INTO shop_product(product_no,product_name,price_cents,stock) VALUES ('AC-ITEM','隔离核销验收商品',500,3)")
        status, response = await request('/api/shop/orders', 'POST', 'user', {
            'items': [{'product_id': 1, 'quantity': 1, 'expected_price_cents': 500}],
            'pay_method': 'mock_alipay', 'request_key': secrets.token_hex(12)})
        assert status == 200
        shop = response['data']
        assert (await request(f"/api/shop/orders/{shop['id']}/pickup-code", role='user'))[0] == 409
        assert (await request(f"/api/payments/{shop['payment_id']}/mock-confirm", 'POST', 'user',
                              {'request_key': secrets.token_hex(12)}))[0] == 200
        for path in (f"/api/reservations/{order['id']}", f"/api/payments/{order['payment_id']}",
                     f"/api/shop/orders/{shop['id']}", f"/api/payments/{shop['payment_id']}",
                     f"/api/shop/orders/{shop['id']}/pickup-code"):
            assert (await request(path, role='other_user'))[0] == 404
        code_path = f"/api/shop/orders/{shop['id']}/pickup-code"
        assert (await request(code_path))[0] == 401
        status, response = await request(code_path, role='user')
        assert status == 200
        code = response['data']['code']
        assert (await request('/api/frontdesk/pickups/lookup', 'POST', 'user', {'code': code}))[0] == 403
        assert (await request('/api/frontdesk/pickups/lookup', 'POST', 'frontdesk', {'code': 'BF-PICKUP:AAAAAAAAAAAA'}))[0] == 404
        assert (await request('/api/frontdesk/pickups/lookup', 'POST', 'frontdesk', {'code': code}))[0] == 200
        assert (await fetch_one(settings, 'SELECT status FROM shop_order WHERE id=%s', (shop['id'],)))['status'] == 'paid'
        assert (await request('/api/frontdesk/pickups/redeem', 'POST', 'frontdesk',
                              {'code': code, 'request_key': secrets.token_hex(12)}))[0] == 200
        assert (await fetch_one(settings, 'SELECT status FROM shop_order WHERE id=%s', (shop['id'],)))['status'] == 'completed'
        assert (await fetch_one(settings, 'SELECT stock,sold_count FROM shop_product WHERE id=1')) == {'stock': 2, 'sold_count': 1}
        checks.append({'cases': ['TC-04', 'TC-28', 'TC-29'], 'result': 'real HTTP ownership and anonymous pickup-code boundaries; unpaid/forged codes rejected; frontdesk lookup does not deliver and authorized redemption changes status without another stock debit'})
        print(json.dumps({'passed': len(checks), 'checks': checks, 'scope': 'owned disposable MySQL; real JWT/HTTP and database-clock boundary tests'}, ensure_ascii=False, indent=2))
    finally:
        if server:
            server.stop()
            await server.close_all_connections()
        client.close()
        await close_pool()
        if created:
            async with con.cursor() as cursor:
                await cursor.execute(f'DROP DATABASE `{name}`')
        con.close()


if __name__ == '__main__':
    asyncio.run(run())
