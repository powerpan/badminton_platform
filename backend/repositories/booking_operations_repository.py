import hashlib
import json
from datetime import datetime

from repositories.database import fetch_all, fetch_one
from repositories.transaction import transaction, audit
from repositories.member_repository import get_or_create_account_for_update, insert_member_transaction_with_cursor
from utils.booking_operations import at, price, validate_attendance
from utils.response import ApiError


async def list_blocks(settings, day_from, day_to, court_id=None, block_type=None, schedule_status=None):
    args = [day_from, day_to]
    where = ''
    if court_id:
        where = ' AND b.court_id = %s'
        args.append(court_id)
    if block_type:
        where += ' AND b.block_type = %s'
        args.append(block_type)
    if schedule_status:
        predicates = {
            'released': "b.status='released'",
            'scheduled': "b.status='active' AND TIMESTAMP(b.reserve_date,b.start_time)>NOW()",
            'in_progress': "b.status='active' AND TIMESTAMP(b.reserve_date,b.start_time)<=NOW() AND TIMESTAMP(b.reserve_date,b.end_time)>NOW()",
            'ended': "b.status='active' AND TIMESTAMP(b.reserve_date,b.end_time)<=NOW()",
        }
        where += ' AND ' + predicates[schedule_status]
    return await fetch_all(settings, '''SELECT b.*, c.court_no, c.court_name FROM court_block b
        JOIN court c ON c.id=b.court_id WHERE b.reserve_date BETWEEN %s AND %s''' + where +
        ' ORDER BY b.reserve_date, b.start_time, b.id', args)


async def blocked(cursor, target):
    await cursor.execute('''SELECT id, reason FROM court_block WHERE court_id=%s AND reserve_date=%s
        AND status='active' AND start_time < %s AND end_time > %s LIMIT 1 FOR UPDATE''',
        (target['court_id'], target['reserve_date'], target['end_time'], target['start_time']))
    return await cursor.fetchone()


async def conflicts(cursor, target, exclude=0):
    await cursor.execute('''SELECT r.id FROM reservation r LEFT JOIN reservation_order ro ON ro.reservation_id=r.id
        WHERE r.court_id=%s AND r.reserve_date=%s AND r.id<>%s
        AND (r.status='confirmed' OR (r.status='pending' AND ro.status='pending' AND ro.expires_at>NOW()))
        AND r.start_time<%s AND r.end_time>%s LIMIT 1 FOR UPDATE''',
        (target['court_id'], target['reserve_date'], exclude, target['end_time'], target['start_time']))
    return await cursor.fetchone()


async def create_block(settings, target, reason, actor, block_type='maintenance'):
    async with transaction(settings) as cursor:
        await cursor.execute('SELECT id FROM court WHERE id=%s FOR UPDATE', (target['court_id'],))
        if not await cursor.fetchone():
            raise ApiError(404, '场地不存在', 404)
        if await conflicts(cursor, target) or await blocked(cursor, target):
            raise ApiError(409, '该时段有有效预约或维护安排，请先处理冲突', 409)
        await cursor.execute('''INSERT INTO court_block (court_id,reserve_date,start_time,end_time,reason,created_by,block_type)
            VALUES (%s,%s,%s,%s,%s,%s,%s)''', (*target.values(), reason, actor['id'], block_type))
        block_id = cursor.lastrowid
        await audit(cursor, actor, 'court', 'block', block_id, {**target, 'reason': reason, 'block_type': block_type})
    return block_id


async def classify_block(settings, block_id, block_type, actor):
    async with transaction(settings) as cursor:
        await cursor.execute('SELECT block_type FROM court_block WHERE id=%s FOR UPDATE', (block_id,))
        row = await cursor.fetchone()
        if not row:
            raise ApiError(404, '维护安排不存在', 404)
        if row['block_type'] == block_type:
            return
        await cursor.execute('UPDATE court_block SET block_type=%s WHERE id=%s', (block_type, block_id))
        await audit(cursor, actor, 'court', 'classify_block', block_id, {'before': row['block_type'], 'after': block_type})


async def release_block(settings, block_id, actor):
    row = await fetch_one(settings, 'SELECT court_id FROM court_block WHERE id=%s', (block_id,))
    if not row:
        raise ApiError(404, '维护安排不存在', 404)
    async with transaction(settings) as cursor:
        await cursor.execute('SELECT id FROM court WHERE id=%s FOR UPDATE', (row['court_id'],))
        await cursor.execute('SELECT status FROM court_block WHERE id=%s FOR UPDATE', (block_id,))
        if (await cursor.fetchone())['status'] == 'released':
            return
        await cursor.execute("UPDATE court_block SET status='released', released_at=NOW(), released_by=%s WHERE id=%s", (actor['id'], block_id))
        await audit(cursor, actor, 'court', 'release', block_id, {'status': 'released'})


async def record_attendance(settings, reservation_id, outcome, actor):
    async with transaction(settings) as cursor:
        await cursor.execute('SELECT * FROM reservation WHERE id=%s FOR UPDATE', (reservation_id,))
        reservation = await cursor.fetchone()
        if not reservation:
            raise ApiError(404, '预约不存在', 404)
        await cursor.execute('SELECT * FROM reservation_attendance WHERE reservation_id=%s', (reservation_id,))
        existing = await cursor.fetchone()
        if existing:
            if existing['outcome'] != outcome:
                raise ApiError(409, '已经记录不同到场结论，不能重复覆盖', 409)
            return
        validate_attendance(reservation, outcome)
        await cursor.execute('INSERT INTO reservation_attendance (reservation_id,outcome,recorded_by) VALUES (%s,%s,%s)',
                             (reservation_id, outcome, actor['id']))
        await audit(cursor, actor, 'reservation', 'attendance', reservation_id, {'outcome': outcome})


async def change_history(settings, reservation_id):
    rows = await fetch_all(settings, '''SELECT id,before_snapshot,after_snapshot,balance_change_cents,
        points_change,pay_method,settlement_delta_cents,created_at FROM reservation_change WHERE reservation_id=%s ORDER BY id DESC''', (reservation_id,))
    for row in rows:
        for key in ('before_snapshot', 'after_snapshot'):
            if isinstance(row[key], str): row[key] = json.loads(row[key])
    court_ids = sorted({row[key]['court_id'] for row in rows for key in ('before_snapshot', 'after_snapshot')})
    if court_ids:
        courts = await fetch_all(settings, 'SELECT id,court_no,court_name FROM court WHERE id IN (' + ','.join(['%s'] * len(court_ids)) + ')', tuple(court_ids))
        names = {court['id']: court for court in courts}
        for row in rows:
            for key in ('before_snapshot', 'after_snapshot'):
                court = names.get(row[key]['court_id'])
                if court:
                    row[key].update(court_no=court['court_no'], court_name=court['court_name'])
    return rows


def snapshot(row):
    return {key: str(row[key]) if key in ('reserve_date', 'start_time', 'end_time') else row[key]
            for key in ('court_id', 'reserve_date', 'start_time', 'end_time', 'payable_amount_cents')}


async def reschedule(settings, *, reservation_id, actor, target, daily_limit, expected_revision, expected_amount, request_key):
    request_hash = hashlib.sha256(json.dumps({**target, 'revision': expected_revision, 'amount': expected_amount},
        sort_keys=True, default=str).encode()).hexdigest()
    async with transaction(settings) as cursor:
        await cursor.execute('SELECT id,status FROM user WHERE id=%s FOR UPDATE', (actor['id'],))
        user = await cursor.fetchone()
        if not user or user['status'] != 1:
            raise ApiError(403, '用户不可用', 403)
        await cursor.execute('SELECT * FROM reservation WHERE id=%s AND user_id=%s', (reservation_id, actor['id']))
        original = await cursor.fetchone()
        if not original:
            raise ApiError(404, '预约不存在', 404)
        for court_id in sorted({original['court_id'], target['court_id']}):
            await cursor.execute('SELECT id FROM court WHERE id=%s FOR UPDATE', (court_id,))
            if not await cursor.fetchone(): raise ApiError(404, '场地不存在', 404)
        await cursor.execute('SELECT * FROM reservation WHERE id=%s FOR UPDATE', (reservation_id,))
        original = await cursor.fetchone()
        await cursor.execute('SELECT request_hash FROM reservation_change WHERE reservation_id=%s AND request_key=%s', (reservation_id, request_key))
        previous = await cursor.fetchone()
        if previous:
            if previous['request_hash'] != request_hash:
                raise ApiError(409, '请求号已用于其他改期，请重新报价', 409)
            return
        if original['status'] != 'confirmed' or at(original['reserve_date'], original['start_time']) <= datetime.now():
            raise ApiError(409, '只有尚未开始的已支付预约可以改期', 409)
        await cursor.execute('SELECT reservation_id FROM reservation_attendance WHERE reservation_id=%s FOR UPDATE', (reservation_id,))
        if await cursor.fetchone(): raise ApiError(409, '已有到场记录，不能改期', 409)
        await cursor.execute('SELECT COALESCE(MAX(id),0) AS revision FROM reservation_change WHERE reservation_id=%s', (reservation_id,))
        if int((await cursor.fetchone())['revision']) != expected_revision:
            raise ApiError(409, '预约已变化，请重新加载并报价', 409)
        if original['court_id'] == target['court_id'] and all(at(original['reserve_date'], original[k]) == at(target['reserve_date'], target[k]) for k in ('start_time','end_time')):
            raise ApiError(400, '新场次与原场次相同', 400)
        await cursor.execute('SELECT * FROM reservation_order WHERE reservation_id=%s FOR UPDATE', (reservation_id,))
        order = await cursor.fetchone()
        await cursor.execute('''SELECT COALESCE(-SUM(balance_change_cents),0) AS net FROM member_account_transaction
            WHERE reservation_id=%s AND transaction_type IN ('reservation_charge','reservation_refund','reservation_reschedule')''', (reservation_id,))
        net = int((await cursor.fetchone())['net'])
        if not order or order['status'] != 'paid' or not order['paid_at'] or order['amount_cents'] != original['payable_amount_cents'] or net != order['amount_cents']:
            raise ApiError(409, '原预约支付流水尚未核对，暂不支持在线改期', 409)
        await cursor.execute('SELECT * FROM court WHERE id=%s FOR UPDATE', (target['court_id'],))
        court = await cursor.fetchone()
        if court['status'] != 1: raise ApiError(409, '目标场地已停用', 409)
        if at(target['reserve_date'], target['start_time']) <= datetime.now():
            raise ApiError(409, '目标时段已经开始', 409)
        if await blocked(cursor, target) or await conflicts(cursor, target, reservation_id):
            raise ApiError(409, '目标时段已被预约或维护占用，原预约保持不变', 409)
        await cursor.execute('''SELECT COUNT(*) AS total FROM reservation WHERE user_id=%s AND reserve_date=%s
            AND id<>%s AND status IN ('pending','confirmed')''', (actor['id'], target['reserve_date'], reservation_id))
        if int((await cursor.fetchone())['total']) >= daily_limit:
            raise ApiError(409, '目标日期预约次数已达上限', 409)
        account = await get_or_create_account_for_update(cursor, actor['id'])
        cost = price(court, account, target)
        if cost['payable_amount_cents'] != expected_amount:
            raise ApiError(409, '价格或会员权益已经变化，请重新报价', 409)
        delta = original['payable_amount_cents'] - cost['payable_amount_cents']
        from repositories.balance_holds import held_balance
        held = await held_balance(cursor,actor['id'])
        balance, points = int(account['balance_cents']), int(account['points'])
        if delta < 0 and balance - held + delta < 0:
            raise ApiError(409, '可用余额不足以支付改期差价', 409)
        points_delta = max(-points, cost['points_awarded'] - original['points_awarded'])
        before = snapshot(original)
        after = snapshot({**target, **cost})
        values = {**target, **cost, 'time_slot': f"{target['start_time']:%H:%M}-{target['end_time']:%H:%M}"}
        await cursor.execute('UPDATE reservation SET ' + ','.join(f'{key}=%s' for key in values) + ' WHERE id=%s', (*values.values(), reservation_id))
        await cursor.execute('UPDATE reservation_order SET amount_cents=%s WHERE id=%s', (cost['payable_amount_cents'], order['id']))
        await cursor.execute('UPDATE member_account SET balance_cents=%s,points=%s WHERE user_id=%s', (balance+delta, points+points_delta, actor['id']))
        await insert_member_transaction_with_cursor(cursor, user_id=actor['id'], reservation_id=reservation_id,
            transaction_type='reservation_reschedule', balance_change_cents=delta, points_change=points_delta,
            balance_before_cents=balance, balance_after_cents=balance+delta, points_before=points, points_after=points+points_delta,
            reason='预约改期差额', operator_id=actor['id'], operator_username=actor.get('username'))
        await cursor.execute('''INSERT INTO reservation_change (reservation_id,request_key,request_hash,before_snapshot,
            after_snapshot,balance_change_cents,points_change,changed_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)''',
            (reservation_id,request_key,request_hash,json.dumps(before),json.dumps(after),delta,points_delta,actor['id']))
        await cursor.execute('''INSERT INTO notification (user_id,title,content,category,source_type,source_id,created_by)
            VALUES (%s,%s,%s,'reservation','reservation',%s,%s)''',
            (actor['id'],'预约改期成功',f"预约 {original['reservation_no']} 已改至 {target['reserve_date']} {court['court_name']} {values['time_slot']}，余额变动 {delta/100:+.2f} 元。",reservation_id,actor['id']))
        await audit(cursor, actor, 'reservation', 'reschedule', reservation_id, {'before': before, 'after': after, 'balance_change_cents': delta})
