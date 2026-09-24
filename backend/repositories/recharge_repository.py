"""Counter recharge: explicit customer, positive mock collection, one wallet credit."""
import json
from datetime import timedelta
from uuid import uuid4

from repositories.database import fetch_one, fetch_all
from repositories.transaction import transaction, audit
from repositories import payment_common as money
from utils.staff_booking import digest, json_value
from utils.response import ApiError
from utils.roles import CUSTOMER_ROLES


def require_counter(actor):
    if actor.get('role') not in ('frontdesk', 'admin'):
        raise ApiError(403, '仅前台和管理员可办理代储值', 403)


def require_scope(actor, order):
    require_counter(actor)
    if actor['role'] != 'admin' and order['operator_id'] != actor['id']:
        raise ApiError(404, '充值单不存在', 404)


def mask_contact(phone):
    if not phone: return ''
    return phone[:3] + '*' * max(4, len(phone) - 7) + phone[-4:] if len(phone) >= 8 else '*' * len(phone)


async def customer(cursor, uid):
    await cursor.execute('SELECT u.id,u.username,u.nickname,u.contact,u.role,u.status,a.balance_cents FROM user u LEFT JOIN member_account a ON a.user_id=u.id WHERE u.id=%s FOR UPDATE', (uid,))
    row = await cursor.fetchone()
    if not row or row['status'] != 1 or row['role'] not in CUSTOMER_ROLES or row['balance_cents'] is None:
        raise ApiError(409, '客户账户不存在、已禁用或不支持充值，请重新确认客户', 409)
    return {'id': row['id'], 'username': row['username'], 'nickname': row['nickname'],
            'contact_masked': mask_contact(row['contact']), 'balance_cents': int(row['balance_cents'])}


async def find_customers(settings, actor, query):
    require_counter(actor)
    async with transaction(settings) as cursor:
        current, _ = await money.lock_people(cursor, actor)
        require_counter(current)
        # No wildcard matching or empty member directory; phone is never returned in full.
        await cursor.execute("""SELECT u.id,u.username,u.nickname,u.contact,a.balance_cents FROM user u
            JOIN member_account a ON a.user_id=u.id WHERE u.status=1 AND u.role IN ('user','admin')
            AND (u.username=%s OR u.contact=%s) ORDER BY u.id LIMIT 20""", (query, query))
        rows = list(await cursor.fetchall())
        return [{'id': row['id'], 'username': row['username'], 'nickname': row['nickname'],
                 'contact_masked': mask_contact(row['contact']), 'balance_cents': int(row['balance_cents'])} for row in rows]


async def locked(cursor, oid, actor=None):
    await cursor.execute('SELECT user_id,operator_id FROM recharge_order WHERE id=%s', (oid,))
    info = await cursor.fetchone()
    if not info: raise ApiError(404, '充值单不存在', 404)
    current = None
    if actor:
        current, _ = await money.lock_people(cursor, actor, info['user_id'])
        require_scope(current, info)
    else:
        await cursor.execute('SELECT id FROM user WHERE id=%s FOR UPDATE', (info['user_id'],))
        await cursor.fetchone()
    await cursor.execute('SELECT *,NOW() AS server_now FROM recharge_order WHERE id=%s FOR UPDATE', (oid,))
    order = await cursor.fetchone()
    await cursor.execute('SELECT * FROM payment_order WHERE recharge_order_id=%s FOR UPDATE', (oid,))
    payments = list(await cursor.fetchall())
    if len(payments) != 1: raise ApiError(409, '充值收款记录不完整，请管理员核对', 409)
    payment = payments[0]
    if payment['customer_user_id'] != order['user_id'] or payment['amount_cents'] != order['amount_cents'] or payment['pay_method'] != 'mock_alipay':
        raise ApiError(409, '充值对象、金额或支付渠道不一致，请管理员核对', 409)
    return current, order, payment


async def details(cursor, order, payment):
    snapshot = json.loads(payment['context_snapshot'])['customer']
    await cursor.execute('''SELECT id,balance_before_cents,balance_after_cents,operator_id,operator_username,created_at
        FROM member_account_transaction WHERE recharge_order_id=%s AND effect_key=%s FOR UPDATE''',
        (order['id'], f"recharge:{order['id']}"))
    effect = await cursor.fetchone()
    return json_value({**{k: order[k] for k in ('id','recharge_no','user_id','amount_cents','status','expires_at',
        'paid_at','canceled_at','operator_id','operator_name_snapshot','created_at','server_now')},
        'customer': snapshot, 'payment_id': payment['id'], 'payment_no': payment['payment_no'],
        'pay_method': payment['pay_method'], 'payment_status': payment['status'], 'credit': effect,
        'payment': {k: payment[k] for k in ('id','payment_no','amount_cents','pay_method','status','purpose','expires_at','paid_at','closed_at')}})


async def close_pending(cursor, order, payment, status):
    if order['status'] != 'pending' or payment['status'] != 'pending':
        raise ApiError(409, '充值与支付状态不一致，请管理员核对', 409)
    now = order['server_now']
    await cursor.execute('UPDATE recharge_order SET status=%s,canceled_at=%s WHERE id=%s',
                         (status, now if status == 'canceled' else None, order['id']))
    await cursor.execute('UPDATE payment_order SET status=%s,closed_at=%s WHERE id=%s', (status, now, payment['id']))
    order.update(status=status, canceled_at=now if status == 'canceled' else None)
    payment.update(status=status, closed_at=now)


async def expire(settings, oid=None):
    ids = await fetch_all(settings, """SELECT r.id FROM recharge_order r JOIN payment_order p ON p.recharge_order_id=r.id
        WHERE r.status='pending' AND p.status='pending' AND (r.expires_at<=NOW() OR p.expires_at<=NOW())"""
        + (' AND r.id=%s' if oid else '') + ' ORDER BY r.id LIMIT 100', (oid,) if oid else ())
    count = 0
    for row in ids:
        async with transaction(settings) as cursor:
            _, order, payment = await locked(cursor, row['id'])
            if order['status'] != 'pending' or payment['status'] != 'pending': continue
            if min(order['expires_at'], payment['expires_at']) > order['server_now']: continue
            await close_pending(cursor, order, payment, 'expired')
            await audit(cursor, {'id': None, 'username': 'system', 'role': 'system'}, 'recharge', 'expire', order['id'], {'payment_id': payment['id']})
            count += 1
    return count


async def create(settings, actor, uid, amount, key, timeout_minutes):
    require_counter(actor)
    request_hash = digest({'user_id': uid, 'amount_cents': amount})
    async with transaction(settings) as cursor:
        current, _ = await money.lock_people(cursor, actor, uid)
        require_counter(current)
        await cursor.execute('SELECT id,request_hash FROM recharge_order WHERE operator_id=%s AND request_key=%s FOR UPDATE', (current['id'], key))
        existing = await cursor.fetchone()
        if existing:
            if existing['request_hash'] != request_hash: raise ApiError(409, '该请求号已用于其他客户或充值金额', 409)
            return existing['id']
        target = await customer(cursor, uid)
        if not 0 < amount <= money.MAX_CENTS - target['balance_cents']:
            raise ApiError(409, '充值金额将超过账户余额上限，请调整金额', 409)
        await cursor.execute('SELECT NOW() AS now')
        now = (await cursor.fetchone())['now']; expires = now + timedelta(minutes=timeout_minutes)
        await cursor.execute('''INSERT INTO recharge_order(recharge_no,user_id,amount_cents,expires_at,operator_id,
            operator_name_snapshot,request_key,request_hash) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)''',
            ('RC'+uuid4().hex, uid, amount, expires, current['id'], current['username'], key, request_hash))
        oid = cursor.lastrowid
        await money.new_payment(cursor, actor=current, customer_id=uid, amount=amount, method='mock_alipay',
            business_key=f'recharge:{oid}', key=key, request_hash=request_hash, expires=expires,
            context={'customer': {k: v for k, v in target.items() if k != 'balance_cents'}, 'amount_cents': amount}, recharge_order_id=oid)
        await audit(cursor, current, 'recharge', 'create', oid, {'customer_user_id': uid, 'amount_cents': amount})
        return oid


async def get(settings, actor, oid):
    require_counter(actor)
    await expire(settings, oid)
    async with transaction(settings) as cursor:
        _, order, payment = await locked(cursor, oid, actor)
        return await details(cursor, order, payment)


async def notification(cursor, order, actor):
    await cursor.execute("""INSERT INTO notification(user_id,title,content,category,source_type,source_id,created_by)
        VALUES (%s,'储值到账',%s,'member','recharge',%s,%s)""",
        (order['user_id'], f"充值单 {order['recharge_no']} 已通过项目内模拟支付宝收款，储值到账 ¥{order['amount_cents']/100:.2f}。可在会员中心查看流水。", order['id'], actor['id']))


async def act(settings, actor, oid, action, key):
    require_counter(actor)
    if action not in ('mock_confirm', 'mock_fail', 'cancel'): raise ApiError(409, '充值单仅支持模拟收款或撤销未付单', 409)
    await expire(settings, oid)
    request_hash = digest({'action': action, 'recharge_order_id': oid})
    async with transaction(settings) as cursor:
        current, order, payment = await locked(cursor, oid, actor)
        result = await money.command_result(cursor, payment['id'], current['id'], key, request_hash)
        if result is not None: return result
        if action == 'mock_confirm' and order['status'] == 'paid' and payment['status'] == 'succeeded':
            result = await details(cursor, order, payment)
        elif action == 'cancel' and order['status'] == 'canceled':
            result = await details(cursor, order, payment)
        elif order['status'] != 'pending' or payment['status'] != 'pending':
            raise ApiError(409, '充值单已收款、关闭或超时，请查看当前结果', 409)
        elif min(order['expires_at'], payment['expires_at']) <= order['server_now']:
            # Do not collect after the deadline even if cleanup has not reached this order yet.
            raise ApiError(409, '收款期限已到，请刷新状态后重新开单', 409)
        else:
            if action == 'cancel':
                await close_pending(cursor, order, payment, 'canceled')
            elif action == 'mock_confirm':
                await customer(cursor, order['user_id'])
                await cursor.execute('SELECT * FROM member_account WHERE user_id=%s FOR UPDATE', (order['user_id'],))
                account = await cursor.fetchone()
                await money.account_effect(cursor, account, current, balance_delta=order['amount_cents'], points_delta=0,
                    effect_key=f"recharge:{oid}", kind='staff_recharge', reason=f"柜台储值 {order['recharge_no']}",
                    payment_id=payment['id'], recharge_id=oid)
                await cursor.execute("UPDATE recharge_order SET status='paid',paid_at=%s WHERE id=%s", (order['server_now'], oid))
                await cursor.execute("UPDATE payment_order SET status='succeeded',paid_at=%s WHERE id=%s", (order['server_now'], payment['id']))
                order.update(status='paid', paid_at=order['server_now']); payment.update(status='succeeded', paid_at=order['server_now'])
                await notification(cursor, order, current)
            await audit(cursor, current, 'recharge', action, oid, {'payment_id': payment['id'], 'customer_user_id': order['user_id'], 'amount_cents': order['amount_cents']})
            result = await details(cursor, order, payment)
        await money.save_command(cursor, payment['id'], current['id'], key, request_hash, action, result)
        return result


async def list_orders(settings, actor, *, date_from, date_to, status, query, page, size):
    require_counter(actor)
    await expire(settings)
    where, args = [], []
    if actor['role'] != 'admin': where.append('r.operator_id=%s'); args.append(actor['id'])
    if date_from: where.append('r.created_at>=%s'); args.append(date_from)
    if date_to: where.append('r.created_at<%s'); args.append(date_to)
    if status: where.append('r.status=%s'); args.append(status)
    if query: where.append('(r.recharge_no=%s OR p.payment_no=%s)'); args.extend([query, query])
    clause = ' AND '.join(where) or '1=1'
    join = 'FROM recharge_order r JOIN payment_order p ON p.recharge_order_id=r.id'
    async with transaction(settings) as cursor:
        current, _ = await money.lock_people(cursor, actor); require_counter(current)
        if current['role'] != actor['role']: raise ApiError(403, '角色已变化，请重新进入工作台', 403)
        await cursor.execute(f'SELECT COUNT(*) AS total {join} WHERE {clause}', args)
        total = (await cursor.fetchone())['total']
        await cursor.execute(f'''SELECT r.*,p.id AS payment_id,p.payment_no,p.pay_method,p.status AS payment_status,
            JSON_EXTRACT(p.context_snapshot,'$.customer') AS customer {join} WHERE {clause}
            ORDER BY r.created_at DESC,r.id DESC LIMIT %s OFFSET %s''', (*args, size, (page-1)*size))
        rows = list(await cursor.fetchall())
        for row in rows:
            row['customer'] = json.loads(row['customer']); row.pop('request_hash'); row.pop('request_key')
        await cursor.execute('SELECT NOW() AS server_now')
        return json_value({'items': rows, 'total': total, 'page': page, 'page_size': size, **await cursor.fetchone()})
