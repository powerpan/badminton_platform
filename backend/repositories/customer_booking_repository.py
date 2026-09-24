"""Online booking settlement for balance and the in-project simulated channel."""
import json
from datetime import datetime, timedelta
from uuid import uuid4

from repositories.database import fetch_one, fetch_all
from repositories.transaction import transaction, audit
from repositories.balance_holds import held_balance
from repositories import payment_common as money
from repositories.member_repository import get_or_create_account_for_update
from repositories.booking_operations_repository import blocked, conflicts, snapshot
from utils.booking_operations import at, price, window
from utils.staff_booking import digest, json_value
from utils.response import ApiError


async def now_at(cursor):
    await cursor.execute('SELECT NOW() AS now')
    return (await cursor.fetchone())['now']


async def initial_payment(settings, rid):
    return await fetch_one(settings,"""SELECT p.* FROM payment_order p JOIN reservation_order ro ON ro.id=p.reservation_order_id
        JOIN reservation r ON r.id=ro.reservation_id WHERE r.id=%s AND r.source='online' AND p.purpose='initial'""",(rid,))


async def link(settings, payment_id):
    return await fetch_one(settings,'''SELECT p.*,r.id AS reservation_id,r.court_id,r.source FROM payment_order p
        JOIN reservation_order ro ON ro.id=p.reservation_order_id JOIN reservation r ON r.id=ro.reservation_id
        WHERE p.id=%s AND r.source='online' ''',(payment_id,))


async def notification(cursor, rid, owner_id, actor, title, text):
    await cursor.execute('''INSERT INTO notification(user_id,title,content,category,source_type,source_id,created_by)
        VALUES (%s,%s,%s,'reservation','reservation',%s,%s)''',(owner_id,title,text,rid,actor['id']))


async def details(cursor, rid, payment_id=None):
    from repositories.reservation_repository import RESERVATION_OPERATIONS_COLUMNS, RESERVATION_ORDER_COLUMNS
    await cursor.execute(f'''SELECT r.*,c.court_no,c.court_name,{RESERVATION_OPERATIONS_COLUMNS},{RESERVATION_ORDER_COLUMNS}
        FROM reservation r JOIN court c ON c.id=r.court_id LEFT JOIN reservation_order ro ON ro.reservation_id=r.id
        WHERE r.id=%s FOR UPDATE''',(rid,))
    result=json_value(await cursor.fetchone())
    if payment_id:
        await cursor.execute('SELECT id,payment_no,amount_cents,pay_method,status,expires_at,paid_at,purpose FROM payment_order WHERE id=%s FOR UPDATE',(payment_id,))
        payment=await cursor.fetchone()
        result['payment']={**json_value(payment),'is_simulated':payment['pay_method']=='mock_alipay'}
    result['server_now']=json_value(await now_at(cursor))
    return result


async def valid_target(cursor, target, rules, owner_id, now, *, exclude=0):
    normalized=window(json_value(target),rules,now=now)
    await cursor.execute('SELECT * FROM court WHERE id=%s FOR UPDATE',(target['court_id'],))
    court=await cursor.fetchone()
    if not court or court['status']!=1: raise ApiError(409,'场地不可用，请重新选择',409)
    if await blocked(cursor,normalized) or await conflicts(cursor,normalized,exclude):
        raise ApiError(409,'目标时段已被预约或维护占用',409)
    await cursor.execute('''SELECT r.id FROM reservation r LEFT JOIN reservation_order ro ON ro.reservation_id=r.id
        WHERE r.user_id=%s AND r.reserve_date=%s AND r.id<>%s
          AND (r.status='confirmed' OR (r.status='pending' AND ro.status='pending' AND ro.expires_at>NOW())) FOR UPDATE''',
        (owner_id,normalized['reserve_date'],exclude))
    if len(await cursor.fetchall())>=rules.daily_reservation_limit: raise ApiError(400,'当天预约次数已达上限',400)
    return court,normalized


async def create(settings, actor, target, rules, method, expected, remark, key):
    request_hash=digest({'target':target,'method':method,'expected':expected,'remark':remark})
    business_key=f"booking:{actor['id']}:{key}"
    async with transaction(settings) as cursor:
        actor,_=await money.lock_people(cursor,actor,customer=True)
        await cursor.execute('''SELECT p.request_hash,ro.reservation_id FROM payment_order p
            JOIN reservation_order ro ON ro.id=p.reservation_order_id WHERE p.business_key=%s''',(business_key,))
        previous=await cursor.fetchone()
        if previous:
            if previous['request_hash']!=request_hash: raise ApiError(409,'该请求号已用于其他预约参数',409)
            return previous['reservation_id']
        # Lock the court before reading clock/availability and the member snapshot.
        await cursor.execute('SELECT id FROM court WHERE id=%s FOR UPDATE',(target['court_id'],))
        now=await now_at(cursor)
        court,target=await valid_target(cursor,target,rules,actor['id'],now)
        account=await get_or_create_account_for_update(cursor,actor['id'])
        cost=price(court,account,target)
        amount=cost['payable_amount_cents']
        if amount!=expected: raise ApiError(409,'场地价格或会员权益已变化，请核对最新金额后重新确认',409)
        if not 0<=amount<=money.MAX_CENTS: raise ApiError(400,'预约金额超出允许范围',400)
        if method=='balance' and account['balance_cents']-await held_balance(cursor,actor['id'])<amount:
            raise ApiError(400,'会员可用余额不足，可选择模拟支付宝或先处理待付款单',400)
        expires=min(now+timedelta(minutes=rules.reservation_payment_timeout_minutes),at(target['reserve_date'],target['start_time']))
        fields={**target,**cost,'reservation_no':'R'+uuid4().hex,'user_id':actor['id'],'status':'pending',
            'time_slot':f"{target['start_time']:%H:%M}-{target['end_time']:%H:%M}",'remark':remark,
            'source':'online','operator_id':actor['id'],'operator_name_snapshot':actor['username']}
        await cursor.execute('INSERT INTO reservation ('+','.join(fields)+') VALUES ('+','.join(['%s']*len(fields))+')',tuple(fields.values()))
        rid=cursor.lastrowid
        await cursor.execute('''INSERT INTO reservation_order(order_no,reservation_id,user_id,amount_cents,pay_method,expires_at,operator_id)
            VALUES (%s,%s,%s,%s,%s,%s,%s)''',('RO'+uuid4().hex,rid,actor['id'],amount,method,expires,actor['id']))
        oid=cursor.lastrowid
        pid=await money.new_payment(cursor,actor=actor,customer_id=actor['id'],amount=amount,method=method,
            business_key=business_key,key=key,request_hash=request_hash,expires=expires,context={'target':target,'cost':cost},reservation_order_id=oid)
        await audit(cursor,actor,'reservation','create',rid,{'payment_id':pid,'amount_cents':amount,'pay_method':method})
        return rid


async def lock_booking(cursor, info):
    await cursor.execute('SELECT * FROM reservation WHERE id=%s FOR UPDATE',(info['reservation_id'],))
    r=await cursor.fetchone()
    if not r or r['source']!='online' or r['user_id']!=info['customer_user_id'] or r['court_id']!=info['court_id']:
        raise ApiError(409,'预约已变化，请刷新原单',409)
    await cursor.execute('SELECT * FROM reservation_order WHERE id=%s FOR UPDATE',(info['reservation_order_id'],))
    order=await cursor.fetchone()
    return r,order


async def lock_payment(cursor,pid):
    await cursor.execute('SELECT * FROM payment_order WHERE id=%s FOR UPDATE',(pid,))
    return await cursor.fetchone()


async def close_pending(cursor,r,order,p,status,now,reason=None):
    await cursor.execute('UPDATE payment_order SET status=%s,closed_at=%s WHERE id=%s',(status,now,p['id']))
    if p['purpose']=='initial':
        await cursor.execute('UPDATE reservation SET status=%s,canceled_at=%s WHERE id=%s',(status,now if status=='canceled' else None,r['id']))
        await cursor.execute('UPDATE reservation_order SET status=%s,canceled_at=%s,cancel_reason=%s WHERE id=%s',
            (status,now if status=='canceled' else None,reason,order['id']))


async def expire(settings, reservation_id=None):
    rows=await fetch_all(settings,'''SELECT p.id FROM payment_order p JOIN reservation_order ro ON ro.id=p.reservation_order_id
        JOIN reservation r ON r.id=ro.reservation_id WHERE r.source='online' AND p.status='pending'
        AND (p.expires_at<=NOW() OR (p.purpose='initial' AND ro.expires_at<=NOW()))'''+
        (' AND r.id=%s' if reservation_id else '')+' ORDER BY p.id LIMIT 100',(reservation_id,) if reservation_id else ())
    total=0
    for row in rows:
        info=await link(settings,row['id'])
        async with transaction(settings) as cursor:
            await cursor.execute('SELECT id FROM user WHERE id=%s FOR UPDATE',(info['customer_user_id'],))
            await cursor.execute('SELECT id FROM court WHERE id=%s FOR UPDATE',(info['court_id'],))
            r,order=await lock_booking(cursor,info)
            p=await lock_payment(cursor,info['id']); now=await now_at(cursor)
            if p['status']=='pending' and (p['expires_at']<=now or (p['purpose']=='initial' and order['expires_at']<=now)):
                await close_pending(cursor,r,order,p,'expired',now)
                await audit(cursor,{'id':None,'role':'system'},'payment','expire',p['id'],{'reservation_id':r['id']})
                total+=1
    return total


async def collect(settings, actor, info, action, key, rules):
    request_hash=digest({'action':action})
    expired=False
    async with transaction(settings) as cursor:
        actor,owner=await money.lock_people(cursor,actor,info['customer_user_id'],customer=True)
        if actor['id']!=info['customer_user_id'] and (actor['role']!='admin' or action=='balance_pay'):
            raise ApiError(404,'支付单不存在',404)
        if owner['status']!=1: raise ApiError(409,'客户账号已停用，不能继续付款',409)
        await cursor.execute('SELECT * FROM court WHERE id=%s FOR UPDATE',(info['court_id'],)); court=await cursor.fetchone()
        # A reschedule payment also locks its target court in sorted order (handled separately).
        r,order=await lock_booking(cursor,info)
        account=await get_or_create_account_for_update(cursor,r['user_id'])
        p=await lock_payment(cursor,info['id'])
        previous=await money.command_result(cursor,p['id'],actor['id'],key,request_hash)
        if previous is not None: return previous
        now=await now_at(cursor)
        if p['purpose']!='initial': raise ApiError(409,'请从改期收款流程确认此支付单',409)
        required='balance' if action=='balance_pay' else 'mock_alipay'
        if p['pay_method']!=required or order['pay_method']!=required:
            raise ApiError(409,'支付渠道与订单不一致，不能改用其他渠道扣款',409)
        if p['status']=='pending' and min(p['expires_at'],order['expires_at'])<=now:
            await close_pending(cursor,r,order,p,'expired',now); expired=True
            await audit(cursor,{'id':None,'role':'system'},'payment','expire',p['id'],{'reservation_id':r['id']})
        elif p['status']=='succeeded' and r['status'] in ('confirmed','completed') and order['status']=='paid' and action!='mock_fail':
            pass
        elif p['status']!='pending' or r['status']!='pending' or order['status']!='pending':
            raise ApiError(409,'订单已关闭或完成，请刷新原单',409)
        elif action=='mock_fail':
            await audit(cursor,actor,'payment','mock_fail',p['id'],{'reservation_id':r['id'],'is_simulated':True})
        else:
            if not court or court['status']!=1 or await blocked(cursor,r) or await conflicts(cursor,r,r['id']):
                raise ApiError(409,'场地状态已变化，请取消待付单并重新安排',409)
            if order['amount_cents']!=p['amount_cents'] or r['payable_amount_cents']!=p['amount_cents']:
                raise ApiError(409,'订单金额与支付快照不一致，请联系管理员',409)
            amount=p['amount_cents']
            if required=='balance' and account['balance_cents']-await held_balance(cursor,r['user_id'],reservation_order_id=order['id'])<amount:
                raise ApiError(409,'可用余额不足，其他有效待付占用须保留',409)
            await money.account_effect(cursor,account,actor,balance_delta=-amount if required=='balance' else 0,
                points_delta=r['points_awarded'],effect_key=f"collection:{p['id']}",kind='reservation_charge',
                reason='预约支付' if required=='balance' else '模拟支付宝订场积分',reservation_id=r['id'],payment_id=p['id'])
            await cursor.execute("UPDATE reservation SET status='confirmed' WHERE id=%s",(r['id'],))
            await cursor.execute("UPDATE reservation_order SET status='paid',paid_at=%s WHERE id=%s",(now,order['id']))
            await cursor.execute("UPDATE payment_order SET status='succeeded',paid_at=%s WHERE id=%s",(now,p['id']))
            await notification(cursor,r['id'],r['user_id'],actor,'预约支付成功',f"预约 {r['reservation_no']} 已付款，{r['reserve_date']} {r['time_slot']}，金额 {amount/100:.2f} 元。")
            await audit(cursor,actor,'payment',action,p['id'],{'reservation_id':r['id'],'amount_cents':amount,'pay_method':required})
        if not expired:
            result=await details(cursor,r['id'],p['id'])
            await money.save_command(cursor,p['id'],actor['id'],key,request_hash,action,result)
    if expired: raise ApiError(409,'订单已超时，场地占用已释放',409)
    return result


async def cancel(settings, actor, info, key, reason, *, by_admin=False):
    request_hash=digest({'action':'cancel','reason':reason})
    async with transaction(settings) as cursor:
        actor,_=await money.lock_people(cursor,actor,info['customer_user_id'],customer=not by_admin,admin=by_admin)
        if not by_admin and actor['id']!=info['customer_user_id']: raise ApiError(404,'预约不存在',404)
        await cursor.execute('SELECT id FROM court WHERE id=%s FOR UPDATE',(info['court_id'],))
        r,order=await lock_booking(cursor,info)
        account=await get_or_create_account_for_update(cursor,r['user_id'])
        p=await lock_payment(cursor,info['id'])
        previous=await money.command_result(cursor,p['id'],actor['id'],key,request_hash)
        if previous is not None: return previous
        now=await now_at(cursor)
        refund=0
        if r['status']=='canceled': pass
        elif r['status']=='pending' and order['status']=='pending' and p['status']=='pending':
            state='expired' if min(order['expires_at'],p['expires_at'])<=now else 'canceled'
            await close_pending(cursor,r,order,p,state,now,reason)
            await audit(cursor,actor,'reservation','cancel',r['id'],{'reason':reason,'status':state})
        elif r['status']=='confirmed' and order['status']=='paid':
            if at(r['reserve_date'],r['end_time'])<=now or (not by_admin and at(r['reserve_date'],r['start_time'])<=now):
                raise ApiError(409,'已开始或已结束的预约不能自行取消',409)
            await cursor.execute('SELECT reservation_id FROM reservation_attendance WHERE reservation_id=%s FOR UPDATE',(r['id'],))
            if await cursor.fetchone(): raise ApiError(409,'已有到场结论，不能取消预约',409)
            payments=await money.payment_balances(cursor,order['id'])
            refund=sum(v['remaining_cents'] for v in payments)
            if refund!=order['amount_cents'] or refund!=r['payable_amount_cents']:
                raise ApiError(409,'支付净额与预约金额不一致，请核对流水',409)
            group=await money.refund_payments(cursor,payments,refund,actor,account,reason=reason,purpose='cancellation',
                key=key,request_hash=request_hash,now=now,reservation_id=r['id'])
            await money.account_effect(cursor,account,actor,balance_delta=0,points_delta=-min(account['points'],r['points_awarded']),
                effect_key=f"cancel-points:{r['id']}",kind='reservation_refund',reason='取消预约退回积分',reservation_id=r['id'],payment_id=p['id'])
            await cursor.execute("UPDATE reservation SET status='canceled',canceled_at=%s WHERE id=%s",(now,r['id']))
            await cursor.execute("UPDATE reservation_order SET status='canceled',canceled_at=%s,cancel_reason=%s WHERE id=%s",(now,reason,order['id']))
            # Close any unconfirmed reschedule supplements; they never moved the booking.
            await cursor.execute("UPDATE payment_order SET status='canceled',closed_at=%s WHERE reservation_order_id=%s AND status='pending'",(now,order['id']))
            await notification(cursor,r['id'],r['user_id'],actor,'预约已取消',f"预约 {r['reservation_no']} 已取消，原渠道退款 {refund/100:.2f} 元。")
            await audit(cursor,actor,'reservation','cancel',r['id'],{'refund_cents':refund,'refund_group_no':group,'reason':reason})
        else: raise ApiError(409,'当前预约状态不能取消',409)
        result=await details(cursor,r['id'],p['id']); result['refund_cents']=refund
        await money.save_command(cursor,p['id'],actor['id'],key,request_hash,'cancel',result)
        return result


async def lock_change_courts(cursor, info, target):
    for court_id in sorted({info['court_id'],target['court_id']}):
        await cursor.execute('SELECT id FROM court WHERE id=%s FOR UPDATE',(court_id,))
        if not await cursor.fetchone(): raise ApiError(404,'目标场地不存在',404)


async def validate_change(cursor,r,order,target,rules,account,revision,expected,now):
    if r['status']!='confirmed' or order['status']!='paid' or at(r['reserve_date'],r['start_time'])<=now:
        raise ApiError(409,'只有尚未开始的已支付预约可以改期',409)
    await cursor.execute('SELECT reservation_id FROM reservation_attendance WHERE reservation_id=%s FOR UPDATE',(r['id'],))
    if await cursor.fetchone(): raise ApiError(409,'已记录到场，不能改期',409)
    await cursor.execute('SELECT id FROM reservation_change WHERE reservation_id=%s ORDER BY id DESC LIMIT 1 FOR UPDATE',(r['id'],))
    previous=await cursor.fetchone()
    if (previous['id'] if previous else 0)!=revision: raise ApiError(409,'预约已变化，请刷新后重新报价',409)
    if r['court_id']==target['court_id'] and all(at(r['reserve_date'],r[k])==at(target['reserve_date'],target[k]) for k in ('start_time','end_time')):
        raise ApiError(400,'新场次与原场次相同',400)
    court,target=await valid_target(cursor,target,rules,r['user_id'],now,exclude=r['id'])
    cost=price(court,account,target)
    if cost['payable_amount_cents']!=expected: raise ApiError(409,'价格或会员权益已变化，请重新报价',409)
    if not 0<=expected<=money.MAX_CENTS: raise ApiError(400,'改期金额超出允许范围',400)
    return target,cost,court


async def apply_change(cursor,r,order,target,cost,actor,account,*,key,request_hash,now,payment_id=None,refund_group=None):
    delta=cost['payable_amount_cents']-r['payable_amount_cents']
    points_delta=max(-account['points'],cost['points_awarded']-r['points_awarded'])
    await money.account_effect(cursor,account,actor,
        balance_delta=-delta if delta>0 and order['pay_method']=='balance' else 0,points_delta=points_delta,
        effect_key=f"change:{r['id']}:{key}",kind='reservation_reschedule',reason='预约改期差额与积分调整',
        reservation_id=r['id'],payment_id=payment_id)
    before=snapshot(r); after=snapshot({**target,**cost})
    values={**target,**cost,'time_slot':f"{target['start_time']:%H:%M}-{target['end_time']:%H:%M}"}
    await cursor.execute('UPDATE reservation SET '+','.join(k+'=%s' for k in values)+' WHERE id=%s',(*values.values(),r['id']))
    await cursor.execute('UPDATE reservation_order SET amount_cents=%s WHERE id=%s',(cost['payable_amount_cents'],order['id']))
    # Other prepared supplements refer to the old revision and cannot remain payable.
    await cursor.execute("UPDATE payment_order SET status='canceled',closed_at=%s WHERE reservation_order_id=%s AND purpose='reschedule' AND status='pending'",(now,order['id']))
    await cursor.execute('''INSERT INTO reservation_change (reservation_id,request_key,request_hash,before_snapshot,after_snapshot,
        balance_change_cents,points_change,changed_by,pay_method,settlement_delta_cents,payment_order_id,refund_group_no)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
        (r['id'],key,request_hash,json.dumps(before),json.dumps(after),-delta if order['pay_method']=='balance' else 0,
         points_delta,actor['id'],order['pay_method'],delta,payment_id,refund_group))
    await notification(cursor,r['id'],r['user_id'],actor,'预约改期成功',
        f"预约 {r['reservation_no']} 已改至 {target['reserve_date']} {values['time_slot']}，结算差额 {delta/100:+.2f} 元。")
    await audit(cursor,actor,'reservation','reschedule',r['id'],{'before':before,'after':after,
        'settlement_delta_cents':delta,'pay_method':order['pay_method'],'refund_group_no':refund_group,'payment_id':payment_id})


async def reschedule(settings,actor,info,target,rules,revision,expected,key):
    request_hash=digest({'target':target,'revision':revision,'expected':expected})
    business_key=f"reschedule:{info['reservation_id']}:{actor['id']}:{key}"
    async with transaction(settings) as cursor:
        actor,_=await money.lock_people(cursor,actor,info['customer_user_id'],customer=True)
        if actor['id']!=info['customer_user_id']: raise ApiError(404,'预约不存在',404)
        await lock_change_courts(cursor,info,target)
        r,order=await lock_booking(cursor,info)
        await cursor.execute('SELECT request_hash FROM reservation_change WHERE reservation_id=%s AND request_key=%s FOR UPDATE',(r['id'],key))
        previous=await cursor.fetchone()
        if previous:
            if previous['request_hash']!=request_hash: raise ApiError(409,'该请求号已用于其他改期参数',409)
            return await details(cursor,r['id'])
        account=await get_or_create_account_for_update(cursor,r['user_id'])
        await cursor.execute('SELECT * FROM payment_order WHERE business_key=%s FOR UPDATE',(business_key,))
        existing=await cursor.fetchone()
        if existing:
            if existing['request_hash']!=request_hash: raise ApiError(409,'该请求号已用于其他改期参数',409)
            if existing['status']!='pending' or existing['expires_at']<=await now_at(cursor):
                raise ApiError(409,'改期补差单已关闭，请重新报价',409)
            result=await details(cursor,r['id'],existing['id']); result['requires_payment']=True
            return result
        now=await now_at(cursor)
        target,cost,court=await validate_change(cursor,r,order,target,rules,account,revision,expected,now)
        payments=await money.payment_balances(cursor,order['id'])
        if sum(p['remaining_cents'] for p in payments)!=order['amount_cents'] or order['amount_cents']!=r['payable_amount_cents']:
            raise ApiError(409,'原预约支付净额不一致，请核对流水',409)
        delta=expected-r['payable_amount_cents']; pid=None; group=None
        if delta>0:
            if order['pay_method']=='balance' and account['balance_cents']-await held_balance(cursor,r['user_id'])<delta:
                raise ApiError(409,'可用余额不足以支付改期差额',409)
            expires=min(now+timedelta(minutes=rules.reservation_payment_timeout_minutes),
                at(r['reserve_date'],r['start_time']),at(target['reserve_date'],target['start_time']))
            pid=await money.new_payment(cursor,actor=actor,customer_id=r['user_id'],amount=delta,method=order['pay_method'],
                business_key=business_key,key=key,request_hash=request_hash,expires=expires,
                context={'target':target,'revision':revision,'expected_amount_cents':expected,'change_key':key,'change_hash':request_hash},
                reservation_order_id=order['id'],purpose='reschedule')
            if order['pay_method']=='mock_alipay':
                await audit(cursor,actor,'payment','reschedule_prepare',pid,{'reservation_id':r['id'],'target':target,'amount_cents':delta})
                result=await details(cursor,r['id'],pid); result['requires_payment']=True
                return result
            await cursor.execute("UPDATE payment_order SET status='succeeded',paid_at=%s WHERE id=%s",(now,pid))
        elif delta<0:
            group=await money.refund_payments(cursor,payments,-delta,actor,account,reason='预约改期退差',purpose='reschedule',
                key=key,request_hash=request_hash,now=now,reservation_id=r['id'])
        await apply_change(cursor,r,order,target,cost,actor,account,key=key,request_hash=request_hash,now=now,payment_id=pid,refund_group=group)
        result=await details(cursor,r['id']); result['requires_payment']=False
        return result


async def collect_change(settings,actor,info,action,key,rules):
    from utils.staff_booking import parse_target
    context=json.loads(info['context_snapshot']); target=parse_target(context['target'])
    request_hash=digest({'action':action}); expired=False
    async with transaction(settings) as cursor:
        actor,owner=await money.lock_people(cursor,actor,info['customer_user_id'],customer=True)
        if actor['id']!=info['customer_user_id'] and actor['role']!='admin': raise ApiError(404,'支付单不存在',404)
        if owner['status']!=1: raise ApiError(409,'客户账号已停用',409)
        await lock_change_courts(cursor,info,target)
        r,order=await lock_booking(cursor,info)
        account=await get_or_create_account_for_update(cursor,r['user_id'])
        p=await lock_payment(cursor,info['id'])
        previous=await money.command_result(cursor,p['id'],actor['id'],key,request_hash)
        if previous is not None: return previous
        if p['pay_method']!='mock_alipay' or action not in ('mock_confirm','mock_fail','cancel'):
            raise ApiError(409,'此补差单须使用原模拟支付宝渠道',409)
        now=await now_at(cursor)
        if p['status']=='pending' and p['expires_at']<=now:
            await close_pending(cursor,r,order,p,'expired',now); expired=True
            await audit(cursor,{'id':None,'role':'system'},'payment','expire',p['id'],{'reservation_id':r['id']})
        elif action=='cancel' and p['status'] in ('pending','canceled'):
            if p['status']=='pending':
                await close_pending(cursor,r,order,p,'canceled',now)
                await audit(cursor,actor,'payment','cancel',p['id'],{'reservation_id':r['id'],'purpose':'reschedule'})
        elif p['paid_at'] is not None and action=='mock_confirm': pass
        elif p['status']!='pending': raise ApiError(409,'改期补差单已关闭',409)
        elif action=='mock_fail':
            await audit(cursor,actor,'payment','mock_fail',p['id'],{'reservation_id':r['id'],'purpose':'reschedule'})
        else:
            target,cost,court=await validate_change(cursor,r,order,target,rules,account,context['revision'],context['expected_amount_cents'],now)
            if cost['payable_amount_cents']-r['payable_amount_cents']!=p['amount_cents']:
                raise ApiError(409,'补差金额已变化，请重新报价',409)
            payments=await money.payment_balances(cursor,order['id'])
            if sum(v['remaining_cents'] for v in payments)!=r['payable_amount_cents']:
                raise ApiError(409,'原预约收款记录不一致',409)
            await cursor.execute("UPDATE payment_order SET status='succeeded',paid_at=%s WHERE id=%s",(now,p['id']))
            await apply_change(cursor,r,order,target,cost,actor,account,key=context['change_key'],request_hash=context['change_hash'],now=now,payment_id=p['id'])
            await audit(cursor,actor,'payment','mock_confirm',p['id'],{'reservation_id':r['id'],'purpose':'reschedule','amount_cents':p['amount_cents']})
        if not expired:
            result=await details(cursor,r['id'],p['id']); result['requires_payment']=p['status']=='pending' and action=='mock_fail'
            await money.save_command(cursor,p['id'],actor['id'],key,request_hash,action,result)
    if expired: raise ApiError(409,'补差付款已超时，原预约保持不变',409)
    return result
