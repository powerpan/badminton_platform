"""Validated administrator-only query contract; HTTP handlers own role authorization."""
from datetime import date, timedelta

from repositories import finance_repository as repository
from services.reservation_service import refresh_reservation_statuses
from utils.response import ApiError
from utils.staff_booking import text_field

ENUMS = {
    'business_type':('reservation','walk_in','walk_in_extension','shop','recharge','reschedule','adjustment'),
    'entry_type':('collection','refund','recharge','adjustment','points','unverified'),
    'pay_method':('balance','mock_alipay','manual','unknown'),
    'status':('pending','succeeded','refunded','canceled','expired','recorded','unverified'),
}


def parse_filters(params):
    try:
        end=date.fromisoformat(str(params.get('date_to') or date.today()))
        start=date.fromisoformat(str(params.get('date_from') or end-timedelta(days=29)))
        if not 0<=(end-start).days<=365: raise ValueError()
        page=int(params.get('page') or 1);size=int(params.get('page_size') or 20)
        if not 1<=page<=2_147_483_647 or not 1<=size<=100: raise ValueError()
        until=end+timedelta(days=1)
    except (TypeError,ValueError,OverflowError) as exc:
        raise ApiError(400,'请使用有效的日期范围（最多 366 天）及分页参数',400) from exc
    filters={'date_from':start,'date_until':until}
    for field,allowed in ENUMS.items():
        value=text_field(params,field,30)
        if value and value not in allowed: raise ApiError(400,f'{field} 筛选值不合法',400)
        filters[field]=value
    for field,maximum in (('customer',50),('operator',50),('order_no',64)):
        filters[field]=text_field(params,field,maximum)
    return filters,page,size


async def list_transactions(settings,params):
    filters,page,size=parse_filters(params)
    await refresh_reservation_statuses(settings)
    result=await repository.list_page(settings,filters,page,size)
    result.update(date_from=str(filters['date_from']),date_to=str(filters['date_until']-timedelta(days=1)))
    return result


async def detail(settings,record_type,record_id):
    if record_type not in repository.RECORD_TYPES:
        raise ApiError(400,'流水来源类型不合法',400)
    await refresh_reservation_statuses(settings)
    return await repository.detail(settings,record_type,record_id)
