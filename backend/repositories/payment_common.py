"""Payment facts, command receipts and account effects; caller owns the transaction."""
import json
from uuid import uuid4

from repositories.member_repository import insert_member_transaction_with_cursor
from utils.staff_booking import json_value
from utils.response import ApiError

MAX_CENTS = 2_147_483_647


async def lock_people(cursor, actor, owner_id=None, *, customer=False, admin=False):
    rows = {}
    for uid in sorted({actor['id'],owner_id or actor['id']}):
        await cursor.execute('SELECT id,username,role,status FROM user WHERE id=%s FOR UPDATE',(uid,))
        rows[uid] = await cursor.fetchone()
    current = rows[actor['id']]
    roles = ('admin',) if admin else ('user','admin') if customer else ('user','admin','frontdesk')
    if not current or current['status']!=1 or current['role'] not in roles:
        raise ApiError(403,'当前账号无权执行此操作',403)
    if owner_id and not rows[owner_id]: raise ApiError(404,'客户账号不存在',404)
    return current, rows.get(owner_id)


async def new_payment(cursor, *, actor, customer_id, amount, method, business_key, key, request_hash,
                      expires, context, reservation_order_id=None, shop_order_id=None, recharge_order_id=None, purpose='initial'):
    if sum(v is not None for v in (reservation_order_id,shop_order_id,recharge_order_id))!=1:
        raise ApiError(400,'支付单须关联唯一业务',400)
    if type(amount) is not int or not 0<=amount<=MAX_CENTS or method not in ('balance','mock_alipay'):
        raise ApiError(400,'支付金额或渠道不合法',400)
    await cursor.execute('''INSERT INTO payment_order (payment_no,reservation_order_id,shop_order_id,recharge_order_id,
        purpose,business_key,customer_user_id,operator_id,operator_name_snapshot,amount_cents,pay_method,
        request_key,request_hash,context_snapshot,expires_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
        ('P'+uuid4().hex,reservation_order_id,shop_order_id,recharge_order_id,purpose,business_key,customer_id,
         actor['id'],actor['username'],amount,method,key,request_hash,json.dumps(json_value(context),ensure_ascii=False),expires))
    return cursor.lastrowid


async def command_result(cursor, payment_id, actor_id, key, request_hash):
    await cursor.execute('''SELECT request_hash,result_snapshot FROM payment_command
        WHERE payment_order_id=%s AND operator_id=%s AND request_key=%s FOR UPDATE''',(payment_id,actor_id,key))
    row=await cursor.fetchone()
    if row:
        if row['request_hash']!=request_hash: raise ApiError(409,'该请求号已用于其他操作或参数',409)
        return json.loads(row['result_snapshot'])
    return None


async def save_command(cursor, payment_id, actor_id, key, request_hash, action, result):
    await cursor.execute('''INSERT INTO payment_command
        (payment_order_id,operator_id,request_key,request_hash,action,result_snapshot) VALUES (%s,%s,%s,%s,%s,%s)''',
        (payment_id,actor_id,key,request_hash,action,json.dumps(json_value(result),ensure_ascii=False)))


async def account_effect(cursor, account, actor, *, balance_delta, points_delta, effect_key, kind, reason,
                         reservation_id=None, shop_order_id=None, payment_id=None, refund_id=None, recharge_id=None):
    balance,points=int(account['balance_cents']),int(account['points'])
    if not 0<=balance+balance_delta<=MAX_CENTS or not 0<=points+points_delta<=MAX_CENTS:
        raise ApiError(409,'账户余额或积分不足，或已达到允许上限',409)
    if not balance_delta and not points_delta: return
    await cursor.execute('UPDATE member_account SET balance_cents=%s,points=%s WHERE user_id=%s',
        (balance+balance_delta,points+points_delta,account['user_id']))
    await insert_member_transaction_with_cursor(cursor,user_id=account['user_id'],reservation_id=reservation_id,
        shop_order_id=shop_order_id,transaction_type=kind,balance_change_cents=balance_delta,points_change=points_delta,
        balance_before_cents=balance,balance_after_cents=balance+balance_delta,points_before=points,points_after=points+points_delta,
        reason=reason,operator_id=actor['id'],operator_username=actor['username'],payment_order_id=payment_id,
        payment_refund_id=refund_id,recharge_order_id=recharge_id,effect_key=effect_key)
    account.update(balance_cents=balance+balance_delta,points=points+points_delta)


async def payment_balances(cursor, reservation_order_id):
    await cursor.execute('''SELECT * FROM payment_order WHERE reservation_order_id=%s
        AND paid_at IS NOT NULL ORDER BY paid_at,id FOR UPDATE''',(reservation_order_id,))
    payments=list(await cursor.fetchall())
    for payment in payments:
        await cursor.execute("SELECT amount_cents FROM payment_refund WHERE payment_order_id=%s AND status='succeeded' FOR UPDATE",(payment['id'],))
        payment['remaining_cents']=payment['amount_cents']-sum(int(r['amount_cents']) for r in await cursor.fetchall())
        if payment['remaining_cents']<0: raise ApiError(409,'历史退款金额不一致，请核对流水',409)
    return payments


async def refund_payments(cursor, payments, amount, actor, account, *, reason, purpose, key, request_hash,
                          now, reservation_id=None, shop_order_id=None):
    if amount<0 or amount>sum(p['remaining_cents'] for p in payments):
        raise ApiError(409,'可退金额不足，请核对原支付记录',409)
    group='RF'+uuid4().hex
    remaining=amount
    for p in payments:
        part=min(remaining,p['remaining_cents'])
        if not part: continue
        await cursor.execute('''INSERT INTO payment_refund (refund_no,payment_order_id,refund_group_no,amount_cents,reason,
            purpose,operator_id,operator_name_snapshot,request_key,request_hash,allocation_key,refunded_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
            ('RF'+uuid4().hex,p['id'],group,part,reason,purpose,actor['id'],actor['username'],key,request_hash,
             f"{group}:{p['id']}",now))
        refund_id=cursor.lastrowid
        if p['pay_method']=='balance':
            await account_effect(cursor,account,actor,balance_delta=part,points_delta=0,effect_key=f'refund:{refund_id}',
                kind='reservation_refund' if reservation_id else 'shop_refund',reason=reason,
                reservation_id=reservation_id,shop_order_id=shop_order_id,payment_id=p['id'],refund_id=refund_id)
        if part==p['remaining_cents']:
            await cursor.execute("UPDATE payment_order SET status='refunded',closed_at=%s WHERE id=%s",(now,p['id']))
        remaining-=part
    return group if amount else None
