import json

from repositories.database import fetch_one
from repositories import customer_booking_repository as online, staff_booking_repository as staff, shop_checkout_repository as shop, recharge_repository as recharge
from services.config_service import get_reservation_rules
from utils.staff_booking import request_key, json_value, text_field
from utils.response import ApiError


async def authorized_payment(settings, actor, payment_id, *, balance=False):
    if actor['role'] not in ('user','admin','frontdesk'): raise ApiError(403,'当前角色无权查看支付单',403)
    row=await fetch_one(settings,'''SELECT p.*,r.id AS reservation_id,r.court_id,r.source
        FROM payment_order p LEFT JOIN reservation_order ro ON ro.id=p.reservation_order_id
        LEFT JOIN reservation r ON r.id=ro.reservation_id WHERE p.id=%s''',(payment_id,))
    if not row: raise ApiError(404,'支付单不存在',404)
    if row['recharge_order_id']:
        recharge.require_scope(actor,row)
        if balance: raise ApiError(409,'代储值仅支持模拟支付宝收款',409)
        return row
    owned=row['customer_user_id']==actor['id']
    staff_scope=actor['role']=='frontdesk' and row['source'] in ('walk_in','walk_in_extension')
    if not (actor['role']=='admin' or owned or staff_scope) or (balance and not owned):
        raise ApiError(404,'支付单不存在',404)
    return row


async def get(settings, actor, payment_id):
    info=await authorized_payment(settings,actor,payment_id)
    if info['recharge_order_id']:
        detail=await recharge.get(settings,actor,info['recharge_order_id'])
        return {**detail['payment'],'business_type':'recharge','recharge_order_id':detail['id'],
            'customer':detail['customer'],'credit':detail['credit'],'server_now':detail['server_now'],
            'refunded_cents':0,'is_simulated':True}
    if info['shop_order_id']: await shop.expire(settings,info['shop_order_id'])
    elif info['source']=='online': await online.expire(settings,info['reservation_id'])
    elif info['source'] in ('walk_in','walk_in_extension'): await staff.expire_pending(settings,info['reservation_id'])
    else: raise ApiError(409,'此支付业务尚未开放',409)
    row=await fetch_one(settings,'''SELECT p.id,payment_no,amount_cents,pay_method,status,purpose,expires_at,paid_at,closed_at,context_snapshot,NOW() AS server_now,
        COALESCE((SELECT SUM(amount_cents) FROM payment_refund WHERE payment_order_id=p.id AND status='succeeded'),0) AS refunded_cents
        FROM payment_order p WHERE p.id=%s''',(payment_id,))
    row['refunded_cents']=int(row['refunded_cents'])
    context=json.loads(row.pop('context_snapshot'))
    if row['purpose']=='reschedule':
        target=context['target']
        court=await fetch_one(settings,'SELECT court_name FROM court WHERE id=%s',(target['court_id'],))
        row['target']={**target,'court_name':court['court_name'] if court else '场地已不可用'}
    return json_value({**row,'reservation_id':info['reservation_id'],'shop_order_id':info['shop_order_id'],'business_type':'recharge' if info['recharge_order_id'] else 'shop' if info['shop_order_id'] else 'reservation',
        'source':info['source'],'is_simulated':row['pay_method']=='mock_alipay'})


async def act(settings, actor, payment_id, action, body):
    if action not in ('balance_pay','mock_confirm','mock_fail','cancel'): raise ApiError(400,'不支持的付款操作',400)
    info=await authorized_payment(settings,actor,payment_id,balance=action=='balance_pay')
    key=request_key(body)
    if action=='cancel' and (info['source']!='online' or info['purpose']!='reschedule'):
        raise ApiError(409,'请在原订单中取消此业务',409)
    if info['recharge_order_id']:
        return await recharge.act(settings,actor,info['recharge_order_id'],action,key)
    if info['shop_order_id']:
        return await shop.collect(settings,actor,info,action,key)
    if info['source']=='online':
        rules=await get_reservation_rules(settings)
        handler=online.collect_change if info['purpose']=='reschedule' else online.collect
        return await handler(settings,actor,info,action,key,rules)
    if info['source'] in ('walk_in','walk_in_extension'):
        return await staff.act(settings,actor,info['reservation_id'],action,key,text_field(body,'reason',255))
    raise ApiError(409,'此支付业务尚未开放',409)
