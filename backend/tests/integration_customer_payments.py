"""Online dual-channel settlement on an owned, disposable MySQL database."""
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
from repositories import database, customer_booking_repository as repo, member_repository
from repositories.database import execute, fetch_one, fetch_all, close_pool
from services import payment_service, reservation_service, booking_operations_service
from utils.response import ApiError


async def run():
    settings = replace(load_settings(), mysql_database='badminton_demo_dual_' + secrets.token_hex(8))
    name = settings.mysql_database
    con = await aiomysql.connect(host=settings.mysql_host, port=settings.mysql_port, user=settings.mysql_user,
                                password=settings.mysql_password, autocommit=True)
    now = datetime(2026, 10, 1, 14, 10)
    created = False
    checks = []
    user = {'id': 2, 'username': 'customer', 'role': 'user'}
    other = {'id': 3, 'username': 'other', 'role': 'user'}
    admin = {'id': 1, 'username': 'admin_test', 'role': 'admin'}
    desk = {'id': 4, 'username': 'desk', 'role': 'frontdesk'}

    async def reject(coro, code=409):
        try:
            await coro
        except ApiError as exc:
            assert exc.status_code == code, (exc.status_code, exc.message)
        else:
            raise AssertionError('Expected rejection')

    def body(court=1, method='mock_alipay', amount=10800, day='2026-10-02', key=None):
        return {'court_id': court, 'reserve_date': day, 'start_time': '15:00', 'end_time': '16:00',
                'pay_method': method, 'expected_amount_cents': amount, 'request_key': key or secrets.token_hex(12)}

    async def create(payload, actor=user):
        return await reservation_service.create_reservation(settings, current_user=actor, body=payload)

    async def act(order, action='mock_confirm', key=None, actor=user):
        return await payment_service.act(settings, actor, order['payment_id'], action,
                                         {'request_key': key or secrets.token_hex(12)})

    async def cancel(order, key=None):
        return await reservation_service.cancel_my_reservation(settings, current_user=user,
            reservation_id=order['id'], body={'request_key': key or secrets.token_hex(12), 'reason': '隔离退款测试'})

    async def account():
        return await fetch_one(settings, 'SELECT balance_cents,points FROM member_account WHERE user_id=2')

    async def change(order, court, amount, key=None):
        payload = {**body(court, amount=amount), 'expected_revision': order.get('revision', 0),
                   'request_key': key or secrets.token_hex(12)}
        return await booking_operations_service.reschedule(settings, order['id'], payload, user)

    try:
        async with con.cursor() as cur:
            await cur.execute(f'CREATE DATABASE `{name}` CHARACTER SET utf8mb4')
            created = True
            await cur.execute(f'USE `{name}`')
            for stmt in re.findall(r'CREATE TABLE IF NOT EXISTS \w+ \(.*?\) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;',
                                   (ROOT / 'sql/init.sql').read_text(), re.S):
                await cur.execute(stmt)
        database._pool = await aiomysql.create_pool(host=settings.mysql_host, port=settings.mysql_port,
            user=settings.mysql_user, password=settings.mysql_password, db=name, minsize=1, maxsize=10,
            autocommit=True, init_command=f'SET timestamp={int(now.timestamp())}')
        await execute(settings, "INSERT INTO user(id,username,password_hash,role) VALUES (1,'admin_test','test-only','admin'),(2,'customer','test-only','user'),(3,'other','test-only','user'),(4,'desk','test-only','frontdesk')")
        for uid in range(1, 5):
            await execute(settings, "INSERT INTO member_account(user_id,member_level,balance_cents,points) VALUES (%s,'gold',100000,200)", (uid,))
        for cid, cost in enumerate([12000, 20000, 5000, 12000, 12000, 12000, 12000, 12000], 1):
            await execute(settings, 'INSERT INTO court(id,court_no,court_name,price_per_hour_cents) VALUES (%s,%s,%s,%s)',
                          (cid, str(cid), '隔离测试场' + str(cid), cost))

        payload = body(key='create-retry-001')
        await reject(create({**payload, 'expected_amount_cents': 12000}))
        a, b = await asyncio.gather(create(payload), create(payload))
        assert a['id'] == b['id'] and a['payable_amount_cents'] == 10800
        await reject(create({**payload, 'remark': '不同参数'}))
        await reject(payment_service.get(settings, other, a['payment_id']), 404)
        await reject(payment_service.get(settings, desk, a['payment_id']), 404)
        await reject(act(a, actor=other), 404)
        await reject(act(a, 'balance_pay'), 409)
        await reject(act(a, 'balance_pay', actor=admin), 404)
        await act(a, 'mock_fail', 'mock-failure-once')
        assert await account() == {'balance_cents': 100000, 'points': 200}
        with patch.object(repo, 'audit', AsyncMock(side_effect=RuntimeError('injected audit failure'))):
            try:
                await act(a, key='fault-payment-001')
            except RuntimeError:
                pass
            else:
                raise AssertionError('Expected injected fault')
        assert (await repo.initial_payment(settings, a['id']))['status'] == 'pending'
        assert await account() == {'balance_cents': 100000, 'points': 200}
        await execute(settings, 'UPDATE court SET price_per_hour_cents=14000 WHERE id=1')
        p1, p2 = await asyncio.gather(act(a, key='concurrent-pay-001'), act(a, key='concurrent-pay-002'))
        assert p1['order_status'] == p2['order_status'] == 'paid' and p1['payable_amount_cents'] == 10800
        await execute(settings, 'UPDATE court SET price_per_hour_cents=12000 WHERE id=1')
        assert await account() == {'balance_cents': 100000, 'points': 308}
        assert len(await fetch_all(settings, "SELECT id FROM member_account_transaction WHERE payment_order_id=%s", (a['payment_id'],))) == 1
        checks.append('member snapshot, duplicate create/pay, owner/channel boundaries and complete audit-fault rollback')

        # Simulated pending orders leave the wallet available; balance pending orders reserve it.
        pending = await create(body(court=4))
        balance = await create(body(court=5, method='balance'))
        held = await member_repository.get_booking_balance(settings, 2)
        assert held['pending_amount_cents'] == 10800, held
        await execute(settings, 'UPDATE member_account SET balance_cents=10800 WHERE user_id=2')
        await reject(create(body(court=6, method='balance', day='2026-10-03')), 400)
        mock = await create(body(court=6, day='2026-10-03'))
        await act(balance, 'balance_pay')
        await act(mock)
        assert (await account())['balance_cents'] == 0
        await cancel(mock)
        assert (await account())['balance_cents'] == 0
        await cancel(balance)
        assert (await account())['balance_cents'] == 10800
        await cancel(pending)
        await execute(settings, 'UPDATE member_account SET balance_cents=100000 WHERE user_id=2')
        checks.append('balance holds exclude simulated orders; both channels retain discounts and refund only their original channel')

        # A supplemental mock payment does not move or hold the target until collection.
        supplement = await change(p1, 2, 18000, 'change-supplement-001')
        assert supplement['requires_payment'] and supplement['court_id'] == 1
        assert supplement['payment']['amount_cents'] == 7200
        supplement_id = supplement['payment']['id']
        saved_account = await account()
        failed = await payment_service.act(settings, user, supplement_id, 'mock_fail', {'request_key': 'supplement-failure-001'})
        assert failed['court_id'] == 1 and failed['payable_amount_cents'] == 10800
        assert failed['payment']['status'] == 'pending' and await account() == saved_account
        contender = await create(body(court=2, amount=18000), other)
        await reject(payment_service.act(settings, user, supplement_id, 'mock_confirm', {'request_key': 'blocked-target-001'}))
        assert (await repo.initial_payment(settings, a['id']))['status'] == 'succeeded'
        await reservation_service.cancel_my_reservation(settings, current_user=other, reservation_id=contender['id'],
                                                      body={'request_key': 'cancel-contender-001'})
        paid = await payment_service.act(settings, user, supplement_id, 'mock_confirm', {'request_key': 'pay-supplement-001'})
        assert paid['court_id'] == 2 and paid['payable_amount_cents'] == 18000
        assert (await account())['balance_cents'] == 100000
        assert paid == await payment_service.act(settings, user, supplement_id, 'mock_confirm', {'request_key': 'pay-supplement-001'})
        checks.append('mock supplement preserves original booking; target conflict is rechecked before atomic payment and move')

        smaller = await change(paid, 3, 4500, 'change-refund-001')
        assert smaller['court_id'] == 3 and smaller['payable_amount_cents'] == 4500
        refunds = await fetch_all(settings, 'SELECT payment_order_id,amount_cents FROM payment_refund WHERE purpose=\'reschedule\' ORDER BY id')
        assert refunds == [{'payment_order_id': a['payment_id'], 'amount_cents': 10800},
                           {'payment_order_id': supplement_id, 'amount_cents': 2700}], refunds
        await reject(change(smaller, 3, 4500, 'same-target-reject'), 400)
        canceled = await cancel(smaller, 'cancel-after-changes')
        assert canceled == await cancel(smaller, 'cancel-after-changes')
        assert canceled['refund_cents'] == 4500 and await account() == {'balance_cents': 100000, 'points': 200}
        totals = await fetch_one(settings, 'SELECT SUM(amount_cents) AS total FROM payment_refund WHERE payment_order_id IN (%s,%s)', (a['payment_id'], supplement_id))
        assert int(totals['total']) == 18000
        checks.append('negative reschedule splits oldest-first refunds; final cancel conserves total cash and points')

        balance = await create(body(method='balance'))
        paid = await act(balance, 'balance_pay')
        raised = await change(paid, 2, 18000)
        assert not raised['requires_payment'] and (await account())['balance_cents'] == 82000
        lowered = await change(raised, 3, 4500)
        assert (await account())['balance_cents'] == 95500
        with patch.object(repo, 'notification', AsyncMock(side_effect=RuntimeError('injected refund failure'))):
            try:
                await cancel(lowered, 'refund-fault-001')
            except RuntimeError:
                pass
            else:
                raise AssertionError('Expected refund fault')
        assert (await account())['balance_cents'] == 95500
        await cancel(lowered)
        assert await account() == {'balance_cents': 100000, 'points': 200}
        checks.append('balance supplements/partial refunds/final cancellation settle once; refund failure rolls back')

        expiring = await create(body(court=7))
        await execute(settings, 'UPDATE payment_order SET expires_at=NOW()-INTERVAL 1 SECOND WHERE id=%s', (expiring['payment_id'],))
        await reject(act(expiring))
        state = await fetch_one(settings, 'SELECT r.status,ro.status AS order_status,p.status AS payment_status FROM reservation r JOIN reservation_order ro ON ro.reservation_id=r.id JOIN payment_order p ON p.reservation_order_id=ro.id WHERE r.id=%s', (expiring['id'],))
        assert set(state.values()) == {'expired'}, state
        active = await create(body(court=7))
        active = await act(active)
        staged = await change(active, 2, 18000)
        await execute(settings, 'UPDATE payment_order SET expires_at=NOW()-INTERVAL 1 SECOND WHERE id=%s', (staged['payment']['id'],))
        await repo.expire(settings)
        current = await fetch_one(settings, 'SELECT court_id,status FROM reservation WHERE id=%s', (active['id'],))
        assert current == {'court_id': 7, 'status': 'confirmed'}
        checks.append('initial expiry releases occupancy; supplement expiry preserves original confirmed booking')
        staged = await change(active, 2, 18000)
        withdrawn = await payment_service.act(settings, user, staged['payment']['id'], 'cancel', {'request_key': 'withdraw-supplement'})
        assert withdrawn['court_id'] == 7 and withdrawn['payment']['status'] == 'canceled'
        stale = await change(active, 2, 18000)
        equal = await change(active, 4, 10800)
        assert equal['court_id'] == 4 and not equal['requires_payment'] and equal['reschedule_payment_id'] is None
        await reject(payment_service.act(settings, user, stale['payment']['id'], 'mock_confirm', {'request_key': 'stale-supplement'}))
        await cancel(equal)
        checks.append('cancel supplement preserves original; equal-price move invalidates old prepared supplements without collecting')
        count = len(await fetch_all(settings, 'SELECT id FROM payment_refund'))
        await execute(settings, 'UPDATE court SET price_per_hour_cents=0 WHERE id=8')
        free = await create(body(court=8, amount=0))
        await act(free)
        await cancel(free)
        assert len(await fetch_all(settings, 'SELECT id FROM payment_refund')) == count
        assert await account() == {'balance_cents': 100000, 'points': 200}
        checks.append('zero-priced online booking closes without inventing refund money or points')

        for method in ('balance', 'mock_alipay'):
            baseline = await account()
            initial = await create(body(method=method))
            current = await act(initial, 'balance_pay' if method == 'balance' else 'mock_confirm')
            for index, (court, amount) in enumerate(((2, 18000), (3, 4500), (2, 18000), (1, 10800))):
                changed = await change(current, court, amount, f'multi-{method}-{index}')
                current = await payment_service.act(settings, user, changed['payment']['id'], 'mock_confirm',
                    {'request_key': f'collect-multi-{method}-{index}'}) if changed['requires_payment'] else changed
                assert current['id'] == initial['id'] and current['payable_amount_cents'] == amount
            await cancel(current, f'final-multi-{method}')
            assert await account() == baseline
            rows = await fetch_all(settings, '''SELECT p.amount_cents,COALESCE(SUM(r.amount_cents),0) AS refunded
                FROM payment_order p JOIN reservation_order o ON o.id=p.reservation_order_id
                LEFT JOIN payment_refund r ON r.payment_order_id=p.id WHERE o.reservation_id=%s
                GROUP BY p.id,p.amount_cents''', (initial['id'],))
            assert len(rows) == 3 and sum(row['amount_cents'] for row in rows) == 31500
            assert all(int(row['refunded']) == row['amount_cents'] for row in rows)
        checks.append('both channels: repeated raises and decreases keep original booking id; final cancellation refunds each of three payments exactly and restores wallet/points')
        print(json.dumps({'passed': True, 'checks': checks, 'database_scope': 'disposable only'}, ensure_ascii=False, indent=2))
    finally:
        await close_pool()
        if created:
            async with con.cursor() as cur:
                await cur.execute(f'DROP DATABASE `{name}`')
        con.close()


if __name__ == '__main__':
    asyncio.run(run())
