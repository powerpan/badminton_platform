from datetime import datetime, timedelta
from repositories import recharge_repository as repository
from repositories.payment_common import MAX_CENTS
from services.config_service import get_reservation_rules
from utils.staff_booking import request_key, text_field
from utils.response import ApiError


async def find_customers(settings, actor, query):
    if not isinstance(query, str) or not 1 <= len(query.strip()) <= 50:
        raise ApiError(400, '请输入完整用户名或登记联系方式查询客户', 400)
    return {'items': await repository.find_customers(settings, actor, query.strip())}


async def create(settings, actor, body):
    if set(body) - {'user_id', 'amount_cents', 'request_key'}:
        raise ApiError(400, '充值仅接受目标客户、金额和请求号，不可调整账户权益', 400)
    uid, amount = body.get('user_id'), body.get('amount_cents')
    if type(uid) is not int or uid <= 0: raise ApiError(400, '请先确认有效客户', 400)
    if type(amount) is not int or not 0 < amount <= MAX_CENTS: raise ApiError(400, '充值金额须为正整数分且不超过允许上限', 400)
    key = request_key(body)
    rules = await get_reservation_rules(settings)
    oid = await repository.create(settings, actor, uid, amount, key, rules.reservation_payment_timeout_minutes)
    return await repository.get(settings, actor, oid)


async def cancel(settings, actor, oid, body):
    return await repository.act(settings, actor, oid, 'cancel', request_key(body))


async def list_orders(settings, actor, params):
    try:
        start = datetime.strptime(params['date_from'], '%Y-%m-%d') if params.get('date_from') else None
        end = datetime.strptime(params['date_to'], '%Y-%m-%d') + timedelta(days=1) if params.get('date_to') else None
        page, size = int(params.get('page') or 1), int(params.get('page_size') or 20)
        if page < 1 or not 1 <= size <= 100 or start and end and start >= end: raise ValueError()
    except (ValueError, TypeError, OverflowError) as exc:
        raise ApiError(400, '日期范围或分页参数不合法', 400) from exc
    status = params.get('status') or None
    if status and status not in ('pending', 'paid', 'canceled', 'expired'): raise ApiError(400, '充值状态不合法', 400)
    return await repository.list_orders(settings, actor, date_from=start, date_to=end, status=status,
        query=text_field(params, 'order_no', 64), page=page, size=size)
