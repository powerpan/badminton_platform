"""Shop stock, money and pickup races on an owned disposable database."""
import asyncio
from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path
import re
import secrets
import sys
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from dotenv import load_dotenv
load_dotenv(ROOT / 'backend/.env')
import aiomysql
from config.settings import load_settings
from repositories import database, shop_checkout_repository as repo, shop_repository as legacy, member_repository
from repositories.database import execute, fetch_one, fetch_all, close_pool
from services import payment_service, shop_service as service, pickup_service
from utils.response import ApiError


async def run():
    settings = replace(load_settings(), mysql_database='badminton_demo_shop_' + secrets.token_hex(8))
    name = settings.mysql_database
    con = await aiomysql.connect(host=settings.mysql_host, port=settings.mysql_port, user=settings.mysql_user,
                                password=settings.mysql_password, autocommit=True)
    now = datetime(2026, 10, 1, 14, 10)
    created = False; checks = []
    admin = {'id': 1, 'username': 'admin_test', 'role': 'admin'}
    user = {'id': 2, 'username': 'customer', 'role': 'user'}
    other = {'id': 3, 'username': 'other', 'role': 'user'}
    desk = {'id': 4, 'username': 'desk', 'role': 'frontdesk'}
    repair = {'id': 5, 'username': 'repair', 'role': 'maintenance'}

    async def reject(coro, code=409):
        try:
            await coro
        except ApiError as exc:
            assert exc.status_code == code, (exc.status_code, exc.message)
        else:
            raise AssertionError('Expected rejection')

    def body(pid=1, quantity=1, method='mock_alipay', key=None, price=1000):
        return {'items': [{'product_id': pid, 'quantity': quantity, 'expected_price_cents': price}],
                'pay_method': method, 'request_key': key or secrets.token_hex(12)}

    async def create(payload=None, actor=user):
        return await service.create_order(settings, current_user=actor, body=payload or body())

    async def pay(order, action='mock_confirm', key=None, actor=user):
        return await payment_service.act(settings, actor, order['payment_id'], action,
                                         {'request_key': key or secrets.token_hex(12)})

    async def account():
        return await fetch_one(settings, 'SELECT balance_cents,points FROM member_account WHERE user_id=2')

    async def state():
        return [await fetch_all(settings, 'SELECT * FROM ' + table + ' ORDER BY ' + key) for table, key in
                [('shop_order', 'id'), ('shop_order_item', 'id'), ('shop_product', 'id'), ('shop_stock_hold', 'id'),
                 ('shop_pickup', 'id'), ('payment_order', 'id'), ('payment_command', 'id'), ('payment_refund', 'id'),
                 ('member_account', 'user_id'), ('member_account_transaction', 'id'), ('operation_log', 'id'), ('notification', 'id')]]

    async def fault(coro, method='audit'):
        before = await state()
        with patch.object(repo, method, AsyncMock(side_effect=RuntimeError('injected fault'))):
            try:
                await coro
            except RuntimeError:
                pass
            else:
                raise AssertionError('Expected injected fault')
        assert await state() == before

    async def refund(order, key='admin-refund-001'):
        return await service.admin_cancel_order(settings, current_user=admin, order_id=order['id'], body={'request_key': key})

    try:
        async with con.cursor() as cur:
            await cur.execute(f'CREATE DATABASE `{name}` CHARACTER SET utf8mb4'); created = True
            await cur.execute(f'USE `{name}`')
            for stmt in re.findall(r'CREATE TABLE IF NOT EXISTS \w+ \(.*?\) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;',
                                   (ROOT / 'sql/init.sql').read_text(), re.S):
                await cur.execute(stmt)
        database._pool = await aiomysql.create_pool(host=settings.mysql_host, port=settings.mysql_port,
            user=settings.mysql_user, password=settings.mysql_password, db=name, minsize=1, maxsize=20,
            autocommit=True, init_command=f'SET timestamp={int(now.timestamp())}')
        await execute(settings, "INSERT INTO user(id,username,password_hash,role) VALUES (1,'admin_test','test-only','admin'),(2,'customer','test-only','user'),(3,'other','test-only','user'),(4,'desk','test-only','frontdesk'),(5,'repair','test-only','maintenance')")
        for uid in range(1, 6):
            await execute(settings, "INSERT INTO member_account(user_id,member_level,balance_cents,points) VALUES (%s,'gold',50000,200)", (uid,))
        for pid in range(1, 6):
            await execute(settings, 'INSERT INTO shop_product(id,product_no,product_name,price_cents,stock) VALUES (%s,%s,%s,1000,10)',
                          (pid, str(pid), '隔离商品' + str(pid)))

        await execute(settings, 'UPDATE member_account SET balance_cents=0 WHERE user_id=2')
        quote = await service.quote_order(settings, current_user=user, body=body())
        assert quote['can_checkout'] and quote['total_amount_cents'] == 1000
        assert not (await service.quote_order(settings, current_user=user, body=body(method='balance')))['can_checkout']
        await reject(create(body(method='balance')), 400)
        await fault(create(body(key='fault-create-001')))
        request = body(key='same-create-request')
        a, b = await asyncio.gather(create(request), create(request))
        assert a['id'] == b['id'] and a['status'] == 'pending' and a['pickup_status'] is None
        assert not await fetch_all(settings, 'SELECT id FROM shop_pickup')
        product = await legacy.get_product(settings, 1)
        assert product['stock'] == 10 and product['reserved_stock'] == 1 and product['available_stock'] == 9
        await reject(create({**request, 'pay_method': 'balance'}))
        await reject(pickup_service.get_code(settings, user, a['id']))
        checks.append('zero-balance mock checkout; no shop discount/points; idempotent creation and pending stock hold without a pickup code')

        await reject(service.update_product(settings, 1, {'stock': 0}))
        await service.update_product(settings, 1, {'price_cents': 1500, 'status': 0})
        await reject(create(body()), 400)
        await reject(pay(a, 'balance_pay'))
        await reject(pay(a, actor=other), 404)
        await reject(payment_service.get(settings, desk, a['payment_id']), 404)
        await reject(pay(a, actor=repair), 403)
        await pay(a, 'mock_fail', 'failed-mock-001')
        assert await account() == {'balance_cents': 0, 'points': 200}
        await fault(pay(a, key='fault-payment-001'), 'ensure_pickup')
        results = await asyncio.gather(*(pay(a, key=f'concurrent-payment-{n:02}') for n in range(20)))
        assert all(r['status'] == 'paid' for r in results)
        assert (await legacy.get_product(settings, 1))['stock'] == 9
        assert (await legacy.get_product(settings, 1))['sold_count'] == 1
        assert len(await fetch_all(settings, 'SELECT id FROM shop_pickup')) == 1
        assert len(await fetch_all(settings, "SELECT id FROM operation_log WHERE module='payment' AND action='mock_confirm'")) == 1
        assert await account() == {'balance_cents': 0, 'points': 200}
        checks.append('stock cannot drop below holds; existing price and delisted pending order still payable; 20 confirmations collect once with rollback on pickup failure')

        credential = await pickup_service.get_code(settings, user, a['id'])
        code = credential['code']
        assert len(code) == 12 and credential['qr_content'] == 'BF-PICKUP:' + code
        assert credential['qr_data_url'].startswith('data:image/svg+xml;base64,')
        await reject(pickup_service.get_code(settings, other, a['id']), 404)
        await reject(pickup_service.lookup(settings, user, {'code': code}), 403)
        before = await state()
        lookup = await pickup_service.lookup(settings, desk, {'code': credential['qr_content']})
        assert lookup['can_redeem'] and 'user_id' not in lookup and 'username' not in lookup
        assert await state() == before
        request_refund = {'request_key': 'request-refund-001', 'reason': '测试退款'}
        await service.request_my_refund(settings, current_user=user, order_id=a['id'], body=request_refund)
        assert (await pickup_service.get_code(settings, user, a['id']))['code'] is None
        await reject(pickup_service.redeem(settings, desk, {'code': code, 'request_key': 'frozen-redeem-001'}))
        await service.reject_refund_request(settings, current_user=admin, order_id=a['id'], body={'request_key': 'reject-refund-001', 'reason': '商品可正常领取'})
        # Replaying a prior request must not freeze the order after that request was rejected.
        await service.request_my_refund(settings, current_user=user, order_id=a['id'], body=request_refund)
        assert (await legacy.get_order(settings, a['id']))['status'] == 'paid'
        assert (await pickup_service.get_code(settings, user, a['id']))['code'] == code
        await fault(pickup_service.redeem(settings, desk, {'code': code, 'request_key': 'fault-redeem-001'}), 'notification')
        d, e = await asyncio.gather(pickup_service.redeem(settings, desk, {'code': code, 'request_key': 'redeem-desk-001'}),
                                    service.complete_order(settings, current_user=admin, order_id=a['id']))
        assert d['status'] == e['status'] == 'completed' and d['redeemed_by_name'] == e['redeemed_by_name']
        assert 'user_id' not in d and (await legacy.get_product(settings, 1))['stock'] == 9
        await reject(refund(a))
        assert code not in json.dumps(await fetch_all(settings, 'SELECT detail FROM operation_log'))
        checks.append('owner-only credential; lookup is read-only; refund freeze/reject restores; retry does not re-freeze; staff/admin concurrent redemption preserves first actor and never re-deducts stock')

        await execute(settings, 'UPDATE member_account SET balance_cents=5000 WHERE user_id=2')
        balance = await create(body(2, method='balance'))
        hold = await create(body(3, quantity=3, method='balance'))
        assert (await member_repository.get_booking_balance(settings, 2))['pending_amount_cents'] == 4000
        await pay(balance, 'balance_pay')
        assert await account() == {'balance_cents': 4000, 'points': 200}
        await reject(create(body(4, quantity=2, method='balance')))
        await fault(refund(balance, 'fault-refund-001'))
        f, g = await asyncio.gather(refund(balance, 'same-refund-key'), refund(balance, 'same-refund-key'))
        assert f == g and f['status'] == 'canceled'
        assert await account() == {'balance_cents': 5000, 'points': 200}
        assert len(await fetch_all(settings, 'SELECT id FROM payment_refund WHERE payment_order_id=%s', (balance['payment_id'],))) == 1
        assert (await legacy.get_product(settings, 2))['stock'] == 10
        await service.cancel_my_order(settings, current_user=user, order_id=hold['id'])
        assert (await member_repository.get_booking_balance(settings, 2))['pending_amount_cents'] == 0
        assert (await legacy.get_product(settings, 3))['stock'] == 10
        checks.append('balance available after other holds; exact debit, audit-fault rollback, refund once and unpaid cancel only releases holds')

        simulated = await create(body(2))
        await pay(simulated)
        before_balance = await account()
        await refund(simulated)
        assert await account() == before_balance and (await legacy.get_product(settings, 2))['stock'] == 10
        pending = await create(body(3))
        await execute(settings, 'UPDATE payment_order SET expires_at=NOW()-INTERVAL 1 SECOND WHERE id=%s', (pending['payment_id'],))
        await reject(pay(pending))
        assert (await legacy.get_order(settings, pending['id']))['status'] == 'expired'
        assert (await legacy.get_product(settings, 3))['available_stock'] == 10
        checks.append('simulated refund never adds wallet money; expired pending collection releases stock without inventing refunds')

        await execute(settings, 'UPDATE shop_product SET stock=1 WHERE id=4')
        contenders = await asyncio.gather(create(body(4)), create(body(4), other), return_exceptions=True)
        winners = [r for r in contenders if isinstance(r, dict)]
        assert len(winners) == 1 and any(isinstance(r, ApiError) for r in contenders)
        winner = winners[0]
        await pay(winner, actor=user if winner['user_id'] == 2 else other)
        assert (await legacy.get_product(settings, 4))['stock'] == 0
        checks.append('last item claimed by two users: exactly one effective hold and one sale')

        await execute(settings, "INSERT INTO shop_product(id,product_no,product_name,price_cents,stock) VALUES (6,'6','隔离过期竞争商品',1000,1)")
        stale = await create(body(6))
        await execute(settings, 'UPDATE payment_order SET expires_at=NOW()-INTERVAL 1 SECOND WHERE id=%s', (stale['payment_id'],))
        outcomes = await asyncio.gather(pay(stale), create(body(6), other), repo.expire(settings), return_exceptions=True)
        assert isinstance(outcomes[0], ApiError) and outcomes[0].status_code == 409
        assert isinstance(outcomes[1], dict) and isinstance(outcomes[2], int), outcomes
        replacement = outcomes[1]
        assert (await legacy.get_order(settings, stale['id']))['status'] == 'expired'
        assert replacement['status'] == 'pending'
        await pay(replacement, actor=other)
        product = await legacy.get_product(settings, 6)
        assert product['stock'] == 0 and product['sold_count'] == 1 and product['reserved_stock'] == 0
        assert len(await fetch_all(settings, 'SELECT id FROM shop_pickup WHERE shop_order_id IN (%s,%s)', (stale['id'], replacement['id']))) == 1
        checks.append('expired last-item payment, new checkout and cleanup race: expired order cannot pay; replacement is the only sale and pickup')

        race = await create(body(5))
        await pay(race)
        race_code = (await pickup_service.get_code(settings, user, race['id']))['code']
        contenders = await asyncio.gather(refund(race), pickup_service.redeem(settings, desk, {'code': race_code, 'request_key': 'refund-redeem-race'}), return_exceptions=True)
        assert sum(isinstance(r, dict) for r in contenders) == 1
        outcome = await legacy.get_order(settings, race['id'])
        assert outcome['status'] in ('canceled', 'completed')
        assert (await legacy.get_product(settings, 5))['stock'] == (10 if outcome['status'] == 'canceled' else 9)
        checks.append('refund versus pickup race: only one legal terminal transition and corresponding stock outcome')

        legacy_id, failure = await legacy.create_paid_order_atomic(settings, order_no='LEGACY-PROVEN', user_id=2,
            items=[{'product_id': 2, 'quantity': 1}], remark='', expected_prices={2: 1000})
        assert failure is None
        old = await legacy.get_order(settings, legacy_id)
        assert old['payment_id'] is None
        old_code = await pickup_service.get_code(settings, user, legacy_id)
        assert old_code['code'] and (await legacy.get_order(settings, legacy_id))['payment_id'] is None
        saved = (await account())['balance_cents']
        await refund(old)
        await refund(old)
        assert (await account())['balance_cents'] == saved + 1000
        unproven = await execute(settings, "INSERT INTO shop_order(order_no,user_id,status,total_amount_cents,pay_method,paid_at) VALUES ('LEGACY-UNKNOWN',2,'paid',1000,'balance',NOW())")
        await execute(settings, "INSERT INTO shop_order_item(order_id,product_id,product_no_snapshot,product_name_snapshot,price_cents,quantity,subtotal_cents) VALUES (%s,2,'2','历史样例',1000,1,1000)", (unproven,))
        before = await state()
        await reject(pickup_service.get_code(settings, user, unproven))
        await reject(refund({'id': unproven}))
        await reject(service.complete_order(settings, current_user=admin, order_id=unproven))
        assert await state() == before
        checks.append('legacy paid order needs original ledger proof, receives no fabricated payment; refund is once; unknown history cannot mint credit or pickup')
        print(json.dumps({'passed': True, 'checks': checks, 'database_scope': 'disposable only'}, ensure_ascii=False, indent=2))
    finally:
        await close_pool()
        if created:
            async with con.cursor() as cur:
                await cur.execute(f'DROP DATABASE `{name}`')
        con.close()


if __name__ == '__main__':
    asyncio.run(run())
