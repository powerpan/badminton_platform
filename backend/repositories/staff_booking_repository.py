"""Guest bookings and simulated collections share the court/transaction boundary.

No member account is read or changed here. Payment command receipts make retries
and simulated failures auditable without relying on a process-local lock.
"""
import json
from datetime import datetime
from uuid import uuid4

from repositories.database import fetch_all, fetch_one
from repositories.transaction import transaction, audit
from repositories.booking_operations_repository import blocked, conflicts
from utils.booking_operations import at
from utils.staff_booking import digest, json_value, original_price, validate_window
from utils.response import ApiError

SOURCES = ('walk_in', 'walk_in_extension')
ORDER_SQL = '''SELECT r.*, c.court_no,c.court_name,ro.id AS order_id,ro.order_no,
    ro.status AS order_status,ro.pay_method AS order_pay_method,
    p.id AS payment_id,p.payment_no,p.amount_cents AS payment_amount_cents,
    p.status AS payment_status,p.expires_at AS payment_expires_at,
    p.paid_at AS payment_paid_at,p.closed_at AS payment_closed_at
    FROM reservation r JOIN court c ON c.id=r.court_id
    JOIN reservation_order ro ON ro.reservation_id=r.id
    JOIN payment_order p ON p.reservation_order_id=ro.id AND p.purpose='initial'
    WHERE r.source IN ('walk_in','walk_in_extension')'''


def public_order(row, now):
    row = dict(row)
    row['payment'] = {'id': row.pop('payment_id'), 'payment_no': row.pop('payment_no'),
        'amount_cents': row.pop('payment_amount_cents'), 'status': row.pop('payment_status'),
        'expires_at': row.pop('payment_expires_at'), 'paid_at': row.pop('payment_paid_at'),
        'closed_at': row.pop('payment_closed_at'), 'pay_method': 'mock_alipay', 'is_simulated': True}
    row['server_now'] = now
    result = json_value(row)
    result['start_time'] = result['start_time'][:5]
    result['end_time'] = result['end_time'][:5]
    return result


async def now_at(cursor):
    await cursor.execute('SELECT NOW() AS now')
    return (await cursor.fetchone())['now']


async def lock_actor(cursor, actor, *, admin=False):
    await cursor.execute('SELECT id,username,role,status FROM user WHERE id=%s FOR UPDATE', (actor['id'],))
    current = await cursor.fetchone()
    allowed = ('admin',) if admin else ('admin', 'frontdesk')
    if not current or current['status'] != 1 or current['role'] not in allowed:
        raise ApiError(403, '当前账号无权执行此操作', 403)
    return current


async def lock_court(cursor, court_id):
    await cursor.execute('SELECT * FROM court WHERE id=%s FOR UPDATE', (court_id,))
    court = await cursor.fetchone()
    if not court: raise ApiError(404, '场地不存在', 404)
    return court


async def prepare(cursor, target, rules, *, parent_id=None):
    parent = None
    if parent_id:
        await cursor.execute("SELECT * FROM reservation WHERE id=%s AND source IN ('walk_in','walk_in_extension')", (parent_id,))
        parent = await cursor.fetchone()
        if not parent: raise ApiError(404, '原散客订场不存在', 404)
        target = {**target, 'court_id': parent['court_id'], 'reserve_date': parent['reserve_date'],
                  'start_time': parent['end_time']}
    court = await lock_court(cursor, target['court_id'])
    now = await now_at(cursor)
    if parent:
        await cursor.execute('SELECT * FROM reservation WHERE id=%s FOR UPDATE', (parent_id,))
        parent = await cursor.fetchone()
        if parent['status'] != 'confirmed' or at(parent['reserve_date'], parent['end_time']) <= now:
            raise ApiError(409, '只有仍有效的已收款散客场次可以续场', 409)
        await cursor.execute("SELECT id FROM reservation_order WHERE reservation_id=%s AND status='paid' AND pay_method='mock_alipay' FOR UPDATE", (parent_id,))
        if not await cursor.fetchone(): raise ApiError(409, '原单尚未收款，不能续场', 409)
    if court['status'] != 1: raise ApiError(409, '场地已停用，请刷新排期', 409)
    expires = validate_window(target, rules, now, extension=bool(parent_id))
    if await blocked(cursor, target) or await conflicts(cursor, target):
        raise ApiError(409, '该时段已被占用或安排维护，请刷新排期', 409)
    return target, court, original_price(court, target), expires, parent, now


async def quote(settings, actor, target, rules, parent_id=None):
    async with transaction(settings) as cursor:
        await lock_actor(cursor, actor)
        target, court, price, expires, parent, now = await prepare(cursor, target, rules, parent_id=parent_id)
        return json_value({**target, **price, 'court_name': court['court_name'],
            'expires_at': expires, 'server_now': now, 'parent_reservation_id': parent_id})


async def create(settings, actor, target, rules, expected_amount, guest, key, parent_id=None):
    business_key = f"walkin:{actor['id']}:{key}"
    request_hash = digest({'target': target, 'expected_amount_cents': expected_amount, 'guest': guest, 'parent_id': parent_id})
    async with transaction(settings) as cursor:
        actor = await lock_actor(cursor, actor)
        await cursor.execute('''SELECT p.request_hash,ro.reservation_id FROM payment_order p
            JOIN reservation_order ro ON ro.id=p.reservation_order_id WHERE p.business_key=%s''', (business_key,))
        previous = await cursor.fetchone()
        if previous:
            if previous['request_hash'] != request_hash:
                raise ApiError(409, '该请求号已用于其他订场参数，请重新核价', 409)
            return previous['reservation_id']
        target, court, cost, expires, parent, now = await prepare(cursor, target, rules, parent_id=parent_id)
        if cost['payable_amount_cents'] != expected_amount:
            raise ApiError(409, '场地价格已变化，请重新核价并确认', 409)
        if parent:
            guest = {k: parent[k] for k in ('guest_name', 'guest_contact')}
        fields = {**target, **cost, 'reservation_no': 'W' + uuid4().hex,
            'time_slot': f"{at(target['reserve_date'],target['start_time']):%H:%M}-{at(target['reserve_date'],target['end_time']):%H:%M}",
            'status': 'pending', 'source': 'walk_in_extension' if parent else 'walk_in',
            'operator_id': actor['id'], 'operator_name_snapshot': actor['username'],
            'parent_reservation_id': parent_id,
            'root_reservation_id': (parent['root_reservation_id'] or parent['id']) if parent else None, **guest}
        await cursor.execute('INSERT INTO reservation (' + ','.join(fields) + ') VALUES (' + ','.join(['%s']*len(fields)) + ')', tuple(fields.values()))
        rid = cursor.lastrowid
        if not parent:
            await cursor.execute('UPDATE reservation SET root_reservation_id=id WHERE id=%s', (rid,))
        await cursor.execute('''INSERT INTO reservation_order
            (order_no,reservation_id,status,amount_cents,pay_method,expires_at,operator_id)
            VALUES (%s,%s,'pending',%s,'mock_alipay',%s,%s)''', ('WO'+uuid4().hex,rid,expected_amount,expires,actor['id']))
        order_id = cursor.lastrowid
        await cursor.execute('''INSERT INTO payment_order
            (payment_no,reservation_order_id,business_key,operator_id,operator_name_snapshot,amount_cents,
             pay_method,request_key,request_hash,context_snapshot,expires_at)
            VALUES (%s,%s,%s,%s,%s,%s,'mock_alipay',%s,%s,%s,%s)''',
            ('MP'+uuid4().hex,order_id,business_key,actor['id'],actor['username'],expected_amount,key,request_hash,
             json.dumps(json_value({'source': fields['source'], 'target': target, 'price': cost, 'parent_reservation_id': parent_id})),expires))
        await audit(cursor, actor, 'reservation', 'walk_in_create', rid,
            {'payment_id': cursor.lastrowid, 'amount_cents': expected_amount, 'parent_reservation_id': parent_id, 'request_key': key})
        return rid


async def lock_booking(cursor, rid):
    await cursor.execute("SELECT court_id FROM reservation WHERE id=%s AND source IN ('walk_in','walk_in_extension')", (rid,))
    link = await cursor.fetchone()
    if not link: raise ApiError(404, '散客订场不存在', 404)
    court = await lock_court(cursor, link['court_id'])
    await cursor.execute('SELECT * FROM reservation WHERE id=%s FOR UPDATE', (rid,))
    reservation = await cursor.fetchone()
    await cursor.execute('SELECT * FROM reservation_order WHERE reservation_id=%s FOR UPDATE', (rid,))
    order = await cursor.fetchone()
    await cursor.execute("SELECT * FROM payment_order WHERE reservation_order_id=%s AND purpose='initial' FOR UPDATE", (order['id'],))
    payment = await cursor.fetchone()
    if not payment or payment['pay_method'] != 'mock_alipay' or payment['shop_order_id'] or payment['recharge_order_id']:
        raise ApiError(409, '订场支付记录不一致，请联系管理员', 409)
    return reservation, order, payment, court


async def close_pending(cursor, r, order, p, status, now, reason=None):
    await cursor.execute('UPDATE reservation SET status=%s,canceled_at=%s WHERE id=%s',
        (status, now if status=='canceled' else None, r['id']))
    await cursor.execute('UPDATE reservation_order SET status=%s,canceled_at=%s,cancel_reason=%s WHERE id=%s',
        (status, now if status=='canceled' else None, reason, order['id']))
    await cursor.execute('UPDATE payment_order SET status=%s,closed_at=%s WHERE id=%s', (status,now,p['id']))


async def expire_locked(cursor, r, order, p, now):
    if p['status'] == 'pending' and (p['expires_at'] <= now or order['expires_at'] <= now):
        await close_pending(cursor,r,order,p,'expired',now)
        await audit(cursor, {'id':None,'role':'system'}, 'payment', 'expire', p['id'], {'reservation_id':r['id']})
        return True
    return False


async def expire_pending(settings, reservation_id=None):
    rows = await fetch_all(settings, '''SELECT r.id FROM payment_order p
        JOIN reservation_order ro ON ro.id=p.reservation_order_id JOIN reservation r ON r.id=ro.reservation_id
        WHERE r.source IN ('walk_in','walk_in_extension') AND p.status='pending'
        AND (p.expires_at<=NOW() OR ro.expires_at<=NOW())''' + (' AND r.id=%s' if reservation_id else '') +
        ' ORDER BY r.id LIMIT 100', (reservation_id,) if reservation_id else ())
    count = 0
    for row in rows:
        async with transaction(settings) as cursor:
            r, order, p, _ = await lock_booking(cursor,row['id'])
            count += await expire_locked(cursor,r,order,p,await now_at(cursor))
    return count


async def get_order(settings, rid):
    await expire_pending(settings, rid)
    row = await fetch_one(settings, ORDER_SQL + ' AND r.id=%s', (rid,))
    if not row: raise ApiError(404, '散客订场不存在', 404)
    result = public_order(row, datetime.now())
    chain = await fetch_all(settings, '''SELECT id,parent_reservation_id,start_time,end_time,status
        FROM reservation WHERE root_reservation_id=%s ORDER BY start_time,id''', (row['root_reservation_id'] or rid,))
    result['chain'] = json_value(chain)
    return result


async def list_orders(settings, day, page, page_size, court_id=None, status=None, query=None):
    await expire_pending(settings)
    where, args = ' AND r.reserve_date=%s', [day]
    for field, value in (('court_id',court_id),('status',status)):
        if value is not None:
            where += f' AND r.{field}=%s'; args.append(value)
    if query:
        where += ' AND (r.reservation_no=%s OR ro.order_no=%s OR p.payment_no=%s)'; args.extend([query]*3)
    total = await fetch_one(settings, 'SELECT COUNT(*) AS total FROM (' + ORDER_SQL + where + ') matched', args)
    rows = await fetch_all(settings, ORDER_SQL + where + ' ORDER BY r.id DESC LIMIT %s OFFSET %s',
        (*args,page_size,(page-1)*page_size))
    return {'items':[public_order(row,datetime.now()) for row in rows], 'total': total['total'], 'page':page,'page_size':page_size}


async def reservation_for_payment(settings, payment_id):
    row = await fetch_one(settings, '''SELECT ro.reservation_id FROM payment_order p
        JOIN reservation_order ro ON ro.id=p.reservation_order_id JOIN reservation r ON r.id=ro.reservation_id
        WHERE p.id=%s AND p.purpose='initial' AND r.source IN ('walk_in','walk_in_extension')''', (payment_id,))
    if not row: raise ApiError(404, '工作范围内的支付单不存在', 404)
    return row['reservation_id']


async def act(settings, actor, rid, action, key, reason=None):
    if action not in ('mock_confirm','mock_fail','cancel','refund'):
        raise ApiError(400, '不支持的操作', 400)
    request_hash = digest({'action':action,'reason':reason})
    expired = False
    async with transaction(settings) as cursor:
        actor = await lock_actor(cursor,actor,admin=action=='refund')
        r, order, p, court = await lock_booking(cursor,rid)
        await cursor.execute('''SELECT request_hash,result_snapshot FROM payment_command
            WHERE payment_order_id=%s AND operator_id=%s AND request_key=%s''', (p['id'],actor['id'],key))
        previous = await cursor.fetchone()
        if previous:
            if previous['request_hash'] != request_hash: raise ApiError(409,'该请求号已用于不同操作或参数',409)
            return json.loads(previous['result_snapshot'])
        now = await now_at(cursor)
        expired = await expire_locked(cursor,r,order,p,now)
        if not expired:
            changed = True
            if action in ('mock_confirm','mock_fail'):
                if action=='mock_confirm' and p['status']=='succeeded' and order['status']=='paid' and r['status'] in ('confirmed','completed'):
                    changed = False
                elif p['status']!='pending' or order['status']!='pending' or r['status']!='pending':
                    raise ApiError(409, '支付单已关闭或完成，请刷新原单', 409)
                elif action=='mock_confirm':
                    if court['status'] != 1 or await blocked(cursor,r) or await conflicts(cursor,r,rid):
                        raise ApiError(409,'场地状态已变化，请取消待付单并重新安排',409)
                    if r['parent_reservation_id']:
                        await cursor.execute('SELECT status FROM reservation WHERE id=%s FOR UPDATE', (r['parent_reservation_id'],))
                        if (await cursor.fetchone())['status']!='confirmed': raise ApiError(409,'原场次已失效，不能收取续场款',409)
                    await cursor.execute("UPDATE reservation SET status='confirmed',opened_at=%s WHERE id=%s", (None if r['parent_reservation_id'] else now,rid))
                    await cursor.execute("UPDATE reservation_order SET status='paid',paid_at=%s WHERE id=%s", (now,order['id']))
                    await cursor.execute("UPDATE payment_order SET status='succeeded',paid_at=%s WHERE id=%s", (now,p['id']))
            elif action=='cancel':
                if p['status']=='canceled' and r['status']=='canceled': changed=False
                elif p['status']!='pending' or r['status']!='pending' or order['status']!='pending':
                    raise ApiError(409,'只能撤销未付款订场；已付款需由管理员处理退款',409)
                else: await close_pending(cursor,r,order,p,'canceled',now,reason)
            elif action=='refund':
                if p['status']=='refunded' and r['status']=='canceled': changed=False
                elif p['status']!='succeeded' or order['status']!='paid' or r['status']!='confirmed' or at(r['reserve_date'],r['end_time'])<=now:
                    raise ApiError(409,'当前散客订单不能退款',409)
                else:
                    await cursor.execute('SELECT reservation_id FROM reservation_attendance WHERE reservation_id=%s FOR UPDATE',(rid,))
                    if await cursor.fetchone(): raise ApiError(409,'已记录到场结论，不能取消',409)
                    await cursor.execute('''SELECT child.id FROM reservation child LEFT JOIN reservation_order co ON co.reservation_id=child.id
                        WHERE child.parent_reservation_id=%s AND (child.status='confirmed' OR
                        (child.status='pending' AND co.status='pending' AND co.expires_at>NOW())) LIMIT 1 FOR UPDATE''',(rid,))
                    if await cursor.fetchone(): raise ApiError(409,'请先处理后续有效续场单，再取消原场次',409)
                    await cursor.execute('SELECT COALESCE(SUM(amount_cents),0) AS refunded FROM payment_refund WHERE payment_order_id=%s AND status=\'succeeded\'',(p['id'],))
                    if (await cursor.fetchone())['refunded'] != 0: raise ApiError(409,'支付单已有退款记录，请核对流水',409)
                    if p['amount_cents'] > 0:
                        number='RF'+uuid4().hex
                        await cursor.execute('''INSERT INTO payment_refund
                            (refund_no,payment_order_id,refund_group_no,amount_cents,reason,purpose,operator_id,
                             operator_name_snapshot,request_key,request_hash,allocation_key,refunded_at)
                            VALUES (%s,%s,%s,%s,%s,'cancellation',%s,%s,%s,%s,%s,%s)''',
                            (number,p['id'],number,p['amount_cents'],reason or '管理员取消散客订场',actor['id'],actor['username'],key,request_hash,f"walkin-refund:{p['id']}",now))
                    await cursor.execute("UPDATE reservation SET status='canceled',canceled_at=%s WHERE id=%s",(now,rid))
                    await cursor.execute("UPDATE reservation_order SET status='canceled',canceled_at=%s,cancel_reason=%s WHERE id=%s",(now,reason,order['id']))
                    await cursor.execute("UPDATE payment_order SET status='refunded',closed_at=%s WHERE id=%s",(now,p['id']))
            if changed:
                await audit(cursor,actor,'payment',action,p['id'],{'reservation_id':rid,'amount_cents':p['amount_cents'],
                    'request_key':key,'reason':reason,'is_simulated':True})
            # A competing actor may have committed while we waited for the court.
            # Use a current read rather than the transaction's earlier MVCC view.
            await cursor.execute(ORDER_SQL + ' AND r.id=%s FOR UPDATE', (rid,))
            result = public_order(await cursor.fetchone(),now)
            result['command_result'] = action
            await cursor.execute('''INSERT INTO payment_command
                (payment_order_id,operator_id,request_key,request_hash,action,result_snapshot) VALUES (%s,%s,%s,%s,%s,%s)''',
                (p['id'],actor['id'],key,request_hash,action,json.dumps(result,ensure_ascii=False)))
    if expired: raise ApiError(409,'收款已超时，场地占用已释放',409)
    return result
