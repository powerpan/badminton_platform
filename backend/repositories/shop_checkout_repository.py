"""Atomic shop checkout, original-channel refunds and whole-order pickup."""
import json
import secrets
from datetime import timedelta
from uuid import uuid4

from repositories import payment_common as money
from repositories.database import fetch_one, fetch_all
from repositories.transaction import transaction, audit
from repositories.balance_holds import held_balance
from repositories.shop_stock import held_quantity, lock_products
from repositories.member_repository import get_or_create_account_for_update
from utils.staff_booking import digest, json_value
from utils.response import ApiError


async def now_at(cursor):
    await cursor.execute('SELECT NOW() AS now')
    return (await cursor.fetchone())['now']


async def info(settings, order_id):
    row = await fetch_one(settings, 'SELECT id,user_id FROM shop_order WHERE id=%s', (order_id,))
    if not row:
        raise ApiError(404, '商城订单不存在', 404)
    items = await fetch_all(settings, 'SELECT product_id FROM shop_order_item WHERE order_id=%s ORDER BY product_id', (order_id,))
    return {**row, 'product_ids': [i['product_id'] for i in items]}


async def lock_order(cursor, scope):
    products = await lock_products(cursor, scope['product_ids'])
    await cursor.execute('SELECT * FROM shop_order WHERE id=%s FOR UPDATE', (scope['id'],))
    order = await cursor.fetchone()
    if not order or order['user_id'] != scope['user_id']:
        raise ApiError(409, '订单信息已变化，请刷新', 409)
    await cursor.execute('SELECT * FROM shop_order_item WHERE order_id=%s ORDER BY product_id,id FOR UPDATE', (order['id'],))
    items = list(await cursor.fetchall())
    if not items or set(i['product_id'] for i in items) != set(scope['product_ids']) or len(products) != len(set(scope['product_ids'])):
        raise ApiError(409, '订单商品资料不完整，请联系管理员核对', 409)
    await cursor.execute('SELECT * FROM payment_order WHERE shop_order_id=%s FOR UPDATE', (order['id'],))
    payment = await cursor.fetchone()
    await cursor.execute('SELECT * FROM shop_pickup WHERE shop_order_id=%s FOR UPDATE', (order['id'],))
    pickup = await cursor.fetchone()
    return order, items, products, payment, pickup


async def details(cursor, order_id):
    from repositories.shop_repository import ORDER_COLUMNS
    await cursor.execute(f'SELECT {ORDER_COLUMNS},NOW() AS server_now FROM shop_order o JOIN user u ON u.id=o.user_id WHERE o.id=%s FOR UPDATE', (order_id,))
    result = await cursor.fetchone()
    await cursor.execute('SELECT * FROM shop_order_item WHERE order_id=%s ORDER BY id FOR UPDATE', (order_id,))
    result['items'] = list(await cursor.fetchall())
    return json_value(result)


async def notification(cursor, order, actor, title, content):
    await cursor.execute("INSERT INTO notification(user_id,title,content,category,source_type,source_id,created_by) VALUES (%s,%s,%s,'shop','shop_order',%s,%s)",
                         (order['user_id'], title, content, order['id'], actor['id']))


async def ensure_pickup(cursor, order_id):
    await cursor.execute('SELECT * FROM shop_pickup WHERE shop_order_id=%s FOR UPDATE', (order_id,))
    pickup = await cursor.fetchone()
    if pickup:
        return pickup
    # Twelve human-readable random symbols; the code never grants staff permissions.
    code = ''.join(secrets.choice('23456789ABCDEFGHJKMNPQRSTUVWXYZ') for _ in range(12))
    await cursor.execute('INSERT INTO shop_pickup(shop_order_id,code) VALUES (%s,%s)', (order_id, code))
    await cursor.execute('SELECT * FROM shop_pickup WHERE shop_order_id=%s FOR UPDATE', (order_id,))
    return await cursor.fetchone()


async def receipt(cursor, order, payment, actor, key, request_hash):
    if payment:
        return await money.command_result(cursor, payment['id'], actor['id'], key, request_hash)
    # Old orders have no payment_order. Preserve that fact; serialize legacy receipts under the order lock.
    await cursor.execute("""SELECT detail FROM operation_log WHERE module='shop' AND action='legacy_command'
        AND target_id=%s AND user_id=%s AND BINARY JSON_UNQUOTE(JSON_EXTRACT(detail,'$.request_key'))=BINARY %s ORDER BY id LIMIT 1 FOR UPDATE""",
        (str(order['id']), actor['id'], key))
    row = await cursor.fetchone()
    if row:
        data = json.loads(row['detail'])
        if data['request_hash'] != request_hash:
            raise ApiError(409, '该请求号已用于其他操作或参数', 409)
        return data['result']
    return None


async def save_receipt(cursor, order, payment, actor, key, request_hash, action, result):
    if payment:
        await money.save_command(cursor, payment['id'], actor['id'], key, request_hash, action, result)
    else:
        await audit(cursor, actor, 'shop', 'legacy_command', order['id'],
                    {'request_key': key, 'request_hash': request_hash, 'action': action, 'result': result})


async def verify_paid(cursor, order, payment):
    if order['paid_at'] is None:
        raise ApiError(409, '缺少原付款依据，请管理员核对历史记录', 409)
    if payment:
        await cursor.execute("SELECT amount_cents FROM payment_refund WHERE payment_order_id=%s AND status='succeeded' FOR UPDATE", (payment['id'],))
        remaining = payment['amount_cents'] - sum(r['amount_cents'] for r in await cursor.fetchall())
        if payment['paid_at'] is None or payment['pay_method'] != order['pay_method'] or remaining != order['total_amount_cents']:
            raise ApiError(409, '原付款净额与订单不一致，请核对流水', 409)
        return [{**payment, 'remaining_cents': remaining}]
    await cursor.execute('SELECT user_id,transaction_type,balance_change_cents FROM member_account_transaction WHERE shop_order_id=%s FOR UPDATE', (order['id'],))
    rows = list(await cursor.fetchall())
    purchases = [r for r in rows if r['transaction_type'] == 'shop_purchase']
    if (order['pay_method'] != 'balance' or not purchases or any(r['user_id'] != order['user_id'] for r in rows)
            or any(r['transaction_type'] != 'shop_purchase' or r['balance_change_cents'] >= 0 for r in rows)
            or -sum(r['balance_change_cents'] for r in purchases) != order['total_amount_cents']):
        raise ApiError(409, '历史订单缺少可核对的原始扣款依据，请管理员核对', 409)
    return []


async def close_pending(cursor, order, payment, status, now, reason=''):
    await cursor.execute('UPDATE shop_order SET status=%s,canceled_at=%s,cancel_reason=%s WHERE id=%s',
                         (status, now if status == 'canceled' else None, reason, order['id']))
    await cursor.execute('UPDATE payment_order SET status=%s,closed_at=%s WHERE id=%s', (status, now, payment['id']))
    await cursor.execute("UPDATE shop_stock_hold SET status='released' WHERE shop_order_id=%s AND status='active'", (order['id'],))


async def expire(settings, order_id=None):
    rows = await fetch_all(settings, """SELECT o.id FROM shop_order o JOIN payment_order p ON p.shop_order_id=o.id
        WHERE o.status='pending' AND p.status='pending' AND (o.expires_at<=NOW() OR p.expires_at<=NOW())"""
        + (' AND o.id=%s' if order_id else '') + ' ORDER BY o.id LIMIT 100', (order_id,) if order_id else ())
    count = 0
    for row in rows:
        scope = await info(settings, row['id'])
        async with transaction(settings) as cursor:
            await cursor.execute('SELECT id FROM user WHERE id=%s FOR UPDATE', (scope['user_id'],))
            order, _, _, p, _ = await lock_order(cursor, scope)
            now = await now_at(cursor)
            if order['status'] == 'pending' and p and p['status'] == 'pending' and min(order['expires_at'], p['expires_at']) <= now:
                await close_pending(cursor, order, p, 'expired', now)
                await audit(cursor, {'id': None, 'role': 'system'}, 'shop', 'expire', order['id'], {'payment_id': p['id']})
                count += 1
    return count


async def create(settings, actor, items, method, remark, key, timeout):
    request_hash = digest({'items': items, 'pay_method': method, 'remark': remark})
    business_key = f"shop:{actor['id']}:{key}"
    async with transaction(settings) as cursor:
        actor, _ = await money.lock_people(cursor, actor, customer=True)
        await cursor.execute('SELECT id,shop_order_id,request_hash FROM payment_order WHERE business_key=%s FOR UPDATE', (business_key,))
        previous = await cursor.fetchone()
        if previous:
            if previous['request_hash'] != request_hash:
                raise ApiError(409, '该请求号已用于不同的购物车或支付渠道', 409)
            return previous['shop_order_id']
        products = await lock_products(cursor, [i['product_id'] for i in items])
        if len(products) != len(items):
            raise ApiError(404, '购物车中有商品不存在', 404)
        total = 0
        for item in items:
            product = products[item['product_id']]
            if product['status'] != 1:
                raise ApiError(400, '商品已下架，不能创建订单', 400)
            if product['stock'] - await held_quantity(cursor, product['id']) < item['quantity']:
                raise ApiError(400, '商品可售库存不足，请调整购买数量', 400)
            if product['price_cents'] != item['expected_price_cents']:
                raise ApiError(409, '商品价格已变化，请重新核对各项价格后确认', 409)
            total += product['price_cents'] * item['quantity']
        if not 0 < total <= money.MAX_CENTS:
            raise ApiError(400, '订单金额超出允许范围', 400)
        account = await get_or_create_account_for_update(cursor, actor['id'])
        if method == 'balance':
            if account['balance_cents'] < total:
                raise ApiError(400, '会员余额不足，可选择模拟支付宝', 400)
            if account['balance_cents'] - await held_balance(cursor, actor['id']) < total:
                raise ApiError(409, '可用余额不足，其他有效待付款占用须保留', 409)
        expires = await now_at(cursor) + timedelta(minutes=timeout)
        await cursor.execute("""INSERT INTO shop_order(order_no,user_id,status,total_amount_cents,pay_method,remark,expires_at,operator_id)
            VALUES (%s,%s,'pending',%s,%s,%s,%s,%s)""", ('S' + uuid4().hex, actor['id'], total, method, remark, expires, actor['id']))
        oid = cursor.lastrowid
        for item in items:
            p = products[item['product_id']]
            await cursor.execute('''INSERT INTO shop_order_item(order_id,product_id,product_no_snapshot,product_name_snapshot,image_url_snapshot,price_cents,quantity,subtotal_cents)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)''', (oid, p['id'], p['product_no'], p['product_name'], p['image_url'], p['price_cents'], item['quantity'], p['price_cents'] * item['quantity']))
            await cursor.execute('INSERT INTO shop_stock_hold(shop_order_id,product_id,quantity,expires_at) VALUES (%s,%s,%s,%s)', (oid, p['id'], item['quantity'], expires))
        pid = await money.new_payment(cursor, actor=actor, customer_id=actor['id'], amount=total, method=method,
            business_key=business_key, key=key, request_hash=request_hash, expires=expires, context={'items': items}, shop_order_id=oid)
        await audit(cursor, actor, 'shop', 'create', oid, {'payment_id': pid, 'amount_cents': total, 'pay_method': method})
        return oid


async def collect(settings, actor, payment_info, action, key):
    scope = await info(settings, payment_info['shop_order_id'])
    request_hash = digest({'action': action})
    expired = False
    async with transaction(settings) as cursor:
        actor, owner = await money.lock_people(cursor, actor, scope['user_id'], customer=True)
        if actor['id'] != scope['user_id'] and (actor['role'] != 'admin' or action == 'balance_pay'):
            raise ApiError(404, '支付单不存在', 404)
        if owner['status'] != 1:
            raise ApiError(409, '客户账号已停用，不能继续付款', 409)
        order, items, products, p, _ = await lock_order(cursor, scope)
        if not p or p['id'] != payment_info['id']:
            raise ApiError(409, '订单与支付记录不一致', 409)
        previous = await receipt(cursor, order, p, actor, key, request_hash)
        if previous is not None:
            return previous
        required = 'balance' if action == 'balance_pay' else 'mock_alipay'
        if p['pay_method'] != required or order['pay_method'] != required:
            raise ApiError(409, '支付渠道与订单不一致', 409)
        now = await now_at(cursor)
        if order['status'] == 'pending' and p['status'] == 'pending' and min(order['expires_at'], p['expires_at']) <= now:
            await close_pending(cursor, order, p, 'expired', now); expired = True
            await audit(cursor, {'id': None, 'role': 'system'}, 'shop', 'expire', order['id'], {'payment_id': p['id']})
        elif p['status'] == 'succeeded' and order['status'] in ('paid', 'completed', 'refund_requested') and action != 'mock_fail':
            pass
        elif order['status'] != 'pending' or p['status'] != 'pending':
            raise ApiError(409, '订单已关闭，请查看最新状态', 409)
        elif action == 'mock_fail':
            await audit(cursor, actor, 'payment', 'mock_fail', p['id'], {'shop_order_id': order['id'], 'is_simulated': True})
        else:
            if p['amount_cents'] != order['total_amount_cents'] or sum(i['subtotal_cents'] for i in items) != p['amount_cents']:
                raise ApiError(409, '订单金额与支付快照不一致', 409)
            await cursor.execute('SELECT * FROM shop_stock_hold WHERE shop_order_id=%s ORDER BY product_id FOR UPDATE', (order['id'],))
            holds = {h['product_id']: h for h in await cursor.fetchall()}
            for item in items:
                hold = holds.get(item['product_id'])
                if not hold or hold['status'] != 'active' or hold['expires_at'] <= now or hold['quantity'] != item['quantity']:
                    raise ApiError(409, '待付库存占用已变化，请取消后重新下单', 409)
                product = products[item['product_id']]
                if product['stock'] - await held_quantity(cursor, product['id'], order['id']) < item['quantity']:
                    raise ApiError(409, '可售库存已变化，不能继续付款', 409)
                if product['sold_count'] + item['quantity'] > money.MAX_CENTS:
                    raise ApiError(409, '商品销量超出允许范围', 409)
            account = await get_or_create_account_for_update(cursor, order['user_id'])
            if required == 'balance':
                if account['balance_cents'] - await held_balance(cursor, order['user_id'], shop_order_id=order['id']) < p['amount_cents']:
                    raise ApiError(409, '可用余额不足，其他有效待付占用须保留', 409)
                await money.account_effect(cursor, account, actor, balance_delta=-p['amount_cents'], points_delta=0,
                    effect_key=f"collection:{p['id']}", kind='shop_purchase', reason='商城余额付款', shop_order_id=order['id'], payment_id=p['id'])
            for item in items:
                await cursor.execute('UPDATE shop_product SET stock=stock-%s,sold_count=sold_count+%s WHERE id=%s', (item['quantity'], item['quantity'], item['product_id']))
            await cursor.execute("UPDATE shop_stock_hold SET status='consumed' WHERE shop_order_id=%s", (order['id'],))
            await cursor.execute("UPDATE shop_order SET status='paid',paid_at=%s WHERE id=%s", (now, order['id']))
            await cursor.execute("UPDATE payment_order SET status='succeeded',paid_at=%s WHERE id=%s", (now, p['id']))
            await ensure_pickup(cursor, order['id'])
            await notification(cursor, order, actor, '商城付款成功', f"订单 {order['order_no']} 已付款，请出示取货码到前台领取商品。")
            await audit(cursor, actor, 'payment', action, p['id'], {'shop_order_id': order['id'], 'amount_cents': p['amount_cents'], 'pay_method': required})
        if not expired:
            result = await details(cursor, order['id'])
            await save_receipt(cursor, order, p, actor, key, request_hash, action, result)
    if expired:
        raise ApiError(409, '订单已超时，库存与余额占用已释放', 409)
    return result


async def action(settings, actor, order_id, action, key, reason='', *, code=None):
    scope = await info(settings, order_id)
    request_hash = digest({'action': action, 'reason': reason, 'code': code})
    async with transaction(settings) as cursor:
        actor, _ = await money.lock_people(cursor, actor, scope['user_id'], admin=action in ('refund', 'reject'), customer=action in ('request_refund', 'cancel'))
        if action == 'redeem' and actor['role'] not in ('admin', 'frontdesk'):
            raise ApiError(403, '当前角色不能核销取货', 403)
        if action in ('request_refund', 'cancel') and actor['id'] != scope['user_id']:
            raise ApiError(404, '商城订单不存在', 404)
        order, items, products, p, pickup = await lock_order(cursor, scope)
        previous = await receipt(cursor, order, p, actor, key, request_hash)
        if previous is not None:
            return previous
        now = await now_at(cursor)
        if action in ('cancel', 'refund') and order['status'] == 'pending' and p and p['status'] == 'pending':
            state = 'expired' if min(order['expires_at'], p['expires_at']) <= now else 'canceled'
            await close_pending(cursor, order, p, state, now, reason)
            await audit(cursor, actor, 'shop', 'cancel', order_id, {'state': state, 'reason': reason})
        elif action == 'refund' and order['status'] in ('paid', 'refund_requested'):
            if pickup and pickup['status'] == 'redeemed':
                raise ApiError(409, '已取货订单不能普通退款', 409)
            payments = await verify_paid(cursor, order, p)
            account = await get_or_create_account_for_update(cursor, order['user_id'])
            if p:
                await money.refund_payments(cursor, payments, order['total_amount_cents'], actor, account,
                    reason=reason, purpose='cancellation', key=key, request_hash=request_hash, now=now, shop_order_id=order_id)
            else:
                await money.account_effect(cursor, account, actor, balance_delta=order['total_amount_cents'], points_delta=0,
                    effect_key=f'legacy-shop-refund:{order_id}', kind='shop_refund', reason=reason, shop_order_id=order_id)
            for item in items:
                product = products[item['product_id']]
                if product['stock'] + item['quantity'] > money.MAX_CENTS or product['sold_count'] < item['quantity']:
                    raise ApiError(409, '商品库存或销量不一致，请先核对', 409)
                await cursor.execute('UPDATE shop_product SET stock=stock+%s,sold_count=sold_count-%s WHERE id=%s', (item['quantity'], item['quantity'], item['product_id']))
            await cursor.execute("UPDATE shop_order SET status='canceled',canceled_at=%s,cancel_reason=%s,refund_reviewed_at=%s WHERE id=%s", (now, reason, now, order_id))
            await cursor.execute("UPDATE shop_pickup SET status='invalid' WHERE shop_order_id=%s", (order_id,))
            await notification(cursor, order, actor, '商城订单已退款', f"订单 {order['order_no']} 按原渠道退款 {order['total_amount_cents']/100:.2f} 元，取货凭证已失效。")
            await audit(cursor, actor, 'shop', 'refund', order_id, {'amount_cents': order['total_amount_cents'], 'pay_method': order['pay_method'], 'reason': reason, 'legacy': p is None})
        elif action in ('refund', 'cancel') and order['status'] in ('canceled', 'expired'):
            pass
        elif action in ('cancel', 'request_refund') and order['status'] == 'paid':
            if pickup and pickup['status'] == 'redeemed':
                raise ApiError(409, '已取货订单不能申请普通退款', 409)
            await cursor.execute("UPDATE shop_order SET status='refund_requested',refund_requested_at=%s,refund_request_reason=%s,refund_reviewed_at=NULL,refund_reject_reason=NULL WHERE id=%s", (now, reason, order_id))
            await cursor.execute("UPDATE shop_pickup SET status='frozen' WHERE shop_order_id=%s", (order_id,))
            await notification(cursor, order, actor, '退款申请已提交', f"订单 {order['order_no']} 等待管理员审核，审核期间暂停取货。")
            await audit(cursor, actor, 'shop', 'refund_request', order_id, {'reason': reason})
        elif action in ('cancel', 'request_refund') and order['status'] == 'refund_requested':
            pass
        elif action == 'reject' and order['status'] == 'refund_requested':
            await cursor.execute("UPDATE shop_order SET status='paid',refund_reviewed_at=%s,refund_reject_reason=%s WHERE id=%s", (now, reason, order_id))
            await cursor.execute("UPDATE shop_pickup SET status='ready' WHERE shop_order_id=%s AND status='frozen'", (order_id,))
            await notification(cursor, order, actor, '退款申请已驳回', f"订单 {order['order_no']} 已恢复取货；原因：{reason}")
            await audit(cursor, actor, 'shop', 'refund_reject', order_id, {'reason': reason})
        elif action == 'redeem' and order['status'] == 'paid':
            await verify_paid(cursor, order, p)
            pickup = pickup or await ensure_pickup(cursor, order_id)
            if pickup['status'] != 'ready' or (code is not None and pickup['code'] != code):
                raise ApiError(409, '取货码无效或当前不可核销', 409)
            await cursor.execute("UPDATE shop_pickup SET status='redeemed',redeemed_by=%s,redeemed_at=%s,redeem_request_key=%s,redeem_request_hash=%s WHERE id=%s", (actor['id'], now, key, request_hash, pickup['id']))
            await cursor.execute("UPDATE shop_order SET status='completed',completed_at=%s WHERE id=%s", (now, order_id))
            await notification(cursor, order, actor, '商品已领取', f"订单 {order['order_no']} 的商品已由前台确认整单交付。")
            await audit(cursor, actor, 'shop', 'redeem', order_id, {'item_count': sum(i['quantity'] for i in items), 'legacy': p is None})
        elif action == 'redeem' and order['status'] == 'completed' and pickup and pickup['status'] == 'redeemed' and (code is None or pickup['code'] == code):
            pass
        else:
            raise ApiError(409, '当前订单状态不允许此操作，请刷新订单', 409)
        result = await details(cursor, order_id)
        if action == 'redeem' and actor['role'] == 'frontdesk':
            result = {k: result[k] for k in ('id', 'order_no', 'status', 'total_amount_cents', 'pickup_status', 'redeemed_at', 'redeemed_by_name', 'items')}
            result['items'] = [{k: i[k] for k in ('product_name_snapshot', 'quantity', 'price_cents', 'subtotal_cents')} for i in result['items']]
        await save_receipt(cursor, order, p, actor, key, request_hash, action, result)
        return result


async def pickup_code(settings, actor, order_id):
    scope = await info(settings, order_id)
    async with transaction(settings) as cursor:
        actor, _ = await money.lock_people(cursor, actor, scope['user_id'], customer=True)
        if actor['role'] != 'admin' and actor['id'] != scope['user_id']:
            raise ApiError(404, '订单不存在', 404)
        order, _, _, p, pickup = await lock_order(cursor, scope)
        if not pickup:
            if order['status'] != 'paid':
                raise ApiError(409, '只有已付款待取货的订单可以生成取货凭证', 409)
            await verify_paid(cursor, order, p)
            pickup = await ensure_pickup(cursor, order_id)
            await audit(cursor, actor, 'shop', 'pickup_issue', order_id, {'legacy': p is None})
        if pickup['status'] == 'ready' and order['status'] != 'paid':
            raise ApiError(409, '订单与取货状态不一致，请刷新', 409)
        # Frozen/invalid/redeemed credentials retain their status, but no usable code is returned.
        return json_value({'order_id': order_id, 'order_no': order['order_no'], 'status': pickup['status'],
            'code': pickup['code'] if pickup['status'] == 'ready' else None,
            'qr_content': 'BF-PICKUP:' + pickup['code'] if pickup['status'] == 'ready' else None,
            'redeemed_by': pickup['redeemed_by'], 'redeemed_at': pickup['redeemed_at']})


async def pickup_lookup(settings, actor, code):
    if actor['role'] not in ('admin', 'frontdesk'):
        raise ApiError(403, '当前角色不能查询取货凭证', 403)
    row = await fetch_one(settings, 'SELECT shop_order_id FROM shop_pickup WHERE code=%s', (code,))
    if not row:
        raise ApiError(404, '取货码不存在，请核对后重试', 404)
    # No mutation, identity disclosure or payment action in the lookup response.
    order = await fetch_one(settings, '''SELECT o.id,o.order_no,o.status,o.total_amount_cents,p.status AS pickup_status,
        p.redeemed_at,u.username AS redeemed_by_name FROM shop_order o JOIN shop_pickup p ON p.shop_order_id=o.id
        LEFT JOIN user u ON u.id=p.redeemed_by WHERE o.id=%s''', (row['shop_order_id'],))
    order['items'] = await fetch_all(settings, 'SELECT product_name_snapshot,quantity,price_cents,subtotal_cents FROM shop_order_item WHERE order_id=%s ORDER BY id', (order['id'],))
    order['can_redeem'] = order['status'] == 'paid' and order['pickup_status'] == 'ready'
    return json_value(order)
