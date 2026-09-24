from datetime import date, datetime

from repositories import staff_booking_repository as repository
from services.config_service import get_reservation_rules
from utils.staff_booking import parse_target, request_key, text_field
from utils.response import ApiError


def target_from(body, parent_id=None):
    if parent_id:
        try:
            return {'end_time': datetime.strptime(str(body['end_time']), '%H:%M').time()}
        except (KeyError, TypeError, ValueError) as exc:
            raise ApiError(400, '请提供 HH:MM 格式的续场结束时间', 400) from exc
    return parse_target(body)


async def quote(settings, actor, body, parent_id=None):
    return await repository.quote(settings,actor,target_from(body,parent_id),await get_reservation_rules(settings),parent_id)


async def create(settings, actor, body, parent_id=None):
    key = request_key(body)
    expected = body.get('expected_amount_cents')
    if type(expected) is not int or not 0 <= expected <= 2_147_483_647:
        raise ApiError(400, '请重新核价并确认整数分金额', 400)
    target = target_from(body,parent_id)
    guest = {k:text_field(body,k) for k in ('guest_name','guest_contact')}
    rid = await repository.create(settings,actor,target,await get_reservation_rules(settings),expected,guest,key,parent_id)
    return await repository.get_order(settings,rid)


async def action(settings, actor, rid, action_name, body):
    return await repository.act(settings,actor,rid,action_name,request_key(body),text_field(body,'reason',255))


async def list_orders(settings, params):
    try:
        day = datetime.strptime(str(params.get('date') or date.today()),'%Y-%m-%d').date()
        page, size = int(params.get('page') or 1), int(params.get('page_size') or 20)
        court_id = int(params['court_id']) if params.get('court_id') else None
        if page < 1 or not 1 <= size <= 100 or (court_id is not None and court_id < 1): raise ValueError()
    except (TypeError,ValueError) as exc:
        raise ApiError(400,'日期、场地或分页参数不合法',400) from exc
    status = params.get('status') or None
    if status and status not in ('pending','confirmed','completed','canceled','expired'):
        raise ApiError(400,'订场状态不合法',400)
    query = text_field(params,'order_no',64)
    return await repository.list_orders(settings,day,page,size,court_id,status,query)
