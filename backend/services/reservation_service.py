import time as time_module
from datetime import date, datetime, time, timedelta
from typing import Any

from config.settings import Settings
from repositories import court_repository, reservation_repository
from services.config_service import get_reservation_rules
from services import notification_service
from services.redis_service import acquire_lock, release_lock, reservation_lock_key
from utils.query import clean_text
from utils.response import ApiError


def _parse_date(value: Any) -> date:
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except ValueError as exc:
        raise ApiError(400, "预约日期格式应为 YYYY-MM-DD", 400) from exc


def _parse_time(value: Any) -> time:
    text = str(value or "").strip()
    try:
        return datetime.strptime(text, "%H:%M").time()
    except ValueError as exc:
        raise ApiError(400, "时间格式应为 HH:MM", 400) from exc


def _time_text(value: Any) -> str:
    if isinstance(value, timedelta):
        total_seconds = int(value.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, _seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}"
    if isinstance(value, time):
        return value.strftime("%H:%M")
    return str(value)[:5]


def _minutes(value: time) -> int:
    return value.hour * 60 + value.minute


def _reservation_no() -> str:
    return "R" + datetime.now().strftime("%Y%m%d%H%M%S") + str(time_module.time_ns() % 1_000_000).zfill(6)


def _reservation_order_no() -> str:
    return "RO" + datetime.now().strftime("%Y%m%d%H%M%S") + str(time_module.time_ns() % 1_000_000).zfill(6)


def _normalize_reservation(row: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(row)
    if "start_time" in normalized:
        normalized["start_time"] = _time_text(normalized["start_time"])
    if "end_time" in normalized:
        normalized["end_time"] = _time_text(normalized["end_time"])
    if isinstance(normalized.get("order_expires_at"), datetime):
        normalized["order_expires_at"] = normalized["order_expires_at"].astimezone().isoformat()
    return normalized


def _validate_status_filter(status: str | None) -> str | None:
    if not status:
        return None
    if status not in {"pending", "confirmed", "canceled", "expired", "completed"}:
        raise ApiError(400, "预约状态参数不合法", 400)
    return status


def _parse_optional_date(value: Any, field_name: str) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ApiError(400, f"{field_name}格式应为 YYYY-MM-DD", 400) from exc


def _parse_optional_int(value: Any, field_name: str) -> int | None:
    if value is None or value == "":
        return None
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ApiError(400, f"{field_name}格式错误", 400) from exc
    if number <= 0:
        raise ApiError(400, f"{field_name}格式错误", 400)
    return number


async def refresh_reservation_statuses(settings: Settings) -> int:
    from repositories.staff_booking_repository import expire_pending
    from repositories.customer_booking_repository import expire
    from repositories.shop_checkout_repository import expire as expire_shop
    from repositories.recharge_repository import expire as expire_recharges
    recharge_expired_count = await expire_recharges(settings)
    shop_expired_count = await expire_shop(settings)
    staff_expired_count = await expire_pending(settings)
    online_expired_count = await expire(settings)
    expired_count = await reservation_repository.expire_pending_reservation_orders(settings)
    completed_count = await reservation_repository.complete_finished_reservations(settings)
    return staff_expired_count + online_expired_count + shop_expired_count + recharge_expired_count + expired_count + completed_count


async def create_reservation(
    settings: Settings,
    *,
    current_user: dict[str, Any],
    body: dict[str, Any],
) -> dict[str, Any]:
    from uuid import uuid4
    from repositories import customer_booking_repository as online
    from utils.staff_booking import parse_target, request_key, text_field
    method=body.get('pay_method','balance')
    if method not in ('balance','mock_alipay'):
        raise ApiError(400,'请选择储值余额或模拟支付宝',400)
    expected=body.get('expected_amount_cents')
    if type(expected) is not int or not 0<=expected<=2_147_483_647:
        raise ApiError(400,'请刷新预约金额后重新确认',400)
    target=parse_target(body)
    # Legacy callers retain balance semantics; new clients send a stable key.
    key=request_key(body) if 'request_key' in body else uuid4().hex
    rid=await online.create(settings,current_user,target,await get_reservation_rules(settings),method,expected,
        text_field(body,'remark',255),key)
    await online.expire(settings,rid)
    detail=await reservation_repository.get_reservation_detail(settings,rid)
    if detail is None: raise ApiError(500,'预约已创建，请通过订单列表查询结果',500)
    return _normalize_reservation(detail)


async def pay_reservation_order(
    settings: Settings,
    *,
    current_user: dict[str, Any],
    order_id: int,
) -> dict[str, Any]:
    from repositories.database import fetch_one
    from services import payment_service
    payment=await fetch_one(settings,"""SELECT p.id FROM payment_order p JOIN reservation_order ro ON ro.id=p.reservation_order_id
        WHERE ro.id=%s AND ro.user_id=%s AND p.purpose='initial'""",(order_id,current_user['id']))
    if payment:
        return await payment_service.act(settings,current_user,payment['id'],'balance_pay',{'request_key':f'legacy-pay-{order_id}'})
    await refresh_reservation_statuses(settings)
    reservation_id, failure_reason = await reservation_repository.pay_reservation_order_atomic(
        settings,
        order_id=order_id,
        user_id=current_user["id"],
        operator_username=current_user.get("username"),
    )
    if failure_reason == "not_found":
        raise ApiError(404, "待支付订单不存在", 404)
    if failure_reason in {"not_pending", "reservation_not_pending"}:
        raise ApiError(400, "当前订单状态不能支付", 400)
    if failure_reason == "expired":
        raise ApiError(400, "待支付订单已超时，场地占用已释放", 400)
    if failure_reason == 'wrong_channel':
        raise ApiError(409,'请使用订单原支付渠道',409)
    if failure_reason == "insufficient_balance":
        raise ApiError(400, "会员余额不足，请联系管理员充值或调整余额", 400)
    if failure_reason == "user_not_found":
        raise ApiError(401, "登录用户不存在，请重新登录", 401)
    if failure_reason == "user_disabled":
        raise ApiError(403, "账号已被禁用", 403)
    if reservation_id is None:
        raise ApiError(409, "订单支付失败，请重试", 409)

    detail = await reservation_repository.get_reservation_detail(settings, reservation_id)
    if detail is None:
        raise ApiError(500, "支付成功但读取预约失败", 500)
    normalized = _normalize_reservation(detail)
    await notification_service.notify_reservation_created(settings, reservation=normalized)
    return normalized


async def get_my_reservation(settings: Settings, *, current_user: dict[str, Any], reservation_id: int) -> dict[str, Any]:
    await refresh_reservation_statuses(settings)
    row = await reservation_repository.get_reservation_detail(settings, reservation_id)
    if row is None or row['user_id'] != current_user['id']:
        raise ApiError(404, '预约不存在', 404)
    return _normalize_reservation(row)


async def my_reservation_summary(settings: Settings, *, current_user: dict[str, Any]) -> dict[str, Any]:
    await refresh_reservation_statuses(settings)
    summary = await reservation_repository.get_user_summary(settings, user_id=current_user["id"])
    return {
        **summary,
        "upcoming": _normalize_reservation(summary["upcoming"]) if summary["upcoming"] else None,
        "pending": _normalize_reservation(summary["pending"]) if summary["pending"] else None,
    }


async def list_my_reservations(
    settings: Settings,
    *,
    current_user: dict[str, Any],
    status_arg: str | None,
    page: int,
    page_size: int,
    offset: int,
) -> dict[str, Any]:
    await refresh_reservation_statuses(settings)
    status = _validate_status_filter(status_arg)
    rows = await reservation_repository.list_user_reservations(
        settings,
        user_id=current_user["id"],
        status=status,
        offset=offset,
        limit=page_size,
    )
    total = await reservation_repository.count_user_reservations(
        settings,
        user_id=current_user["id"],
        status=status,
    )
    return {"items": [_normalize_reservation(row) for row in rows], "total": total, "page": page, "page_size": page_size}


async def cancel_my_reservation(
    settings: Settings,
    *,
    current_user: dict[str, Any],
    reservation_id: int,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    await refresh_reservation_statuses(settings)
    reservation = await reservation_repository.get_reservation_detail(settings, reservation_id)
    if reservation is None or reservation["user_id"] != current_user["id"]:
        raise ApiError(404, "预约记录不存在", 404)
    from repositories import customer_booking_repository as online
    from utils.staff_booking import request_key, text_field
    payment=await online.initial_payment(settings,reservation_id)
    if payment:
        payload=body or {}
        key=request_key(payload) if 'request_key' in payload else f'cancel-online-{reservation_id}'
        info=await online.link(settings,payment['id'])
        return await online.cancel(settings,current_user,info,key,text_field(payload,'reason',255) or '用户取消预约')
    if reservation["status"] not in {"pending", "confirmed"}:
        raise ApiError(400, "当前预约状态不能取消", 400)
    reserve_date = reservation["reserve_date"]
    start_time = reservation["start_time"]
    start_dt = datetime.combine(reserve_date, start_time if isinstance(start_time, time) else (datetime.min + start_time).time())
    if start_dt <= datetime.now():
        raise ApiError(400, "已开始或已过期的预约不能取消", 400)
    _canceled_id, failure_reason, refund_cents = await reservation_repository.cancel_reservation_atomic(
        settings,
        reservation_id,
        operator_id=current_user.get("id"),
        operator_username=current_user.get("username"),
        reason="用户取消预约" if reservation["status"] == "pending" else "用户取消预约退款",
        require_future=True,
    )
    if failure_reason == "not_found":
        raise ApiError(404, "预约记录不存在", 404)
    if failure_reason in {"attendance_recorded", "already_started"}:
        raise ApiError(409, "预约已到场或已开始，不能取消", 409)
    if failure_reason == "not_confirmed":
        raise ApiError(400, "当前预约状态不能取消", 400)
    updated = await reservation_repository.get_reservation_detail(settings, reservation_id)
    if updated is None:
        raise ApiError(404, "预约记录不存在", 404)
    normalized = _normalize_reservation(updated)
    normalized["refund_cents"] = refund_cents
    await notification_service.notify_reservation_canceled(
        settings,
        reservation=normalized,
        by_admin=False,
        operator_id=current_user.get("id"),
    )
    return normalized


async def list_admin_reservations(
    settings: Settings,
    *,
    status_arg: str | None,
    page: int,
    page_size: int,
    offset: int,
    username_arg: Any = None,
    court_id_arg: Any = None,
    date_from_arg: Any = None,
    date_to_arg: Any = None,
    source_arg: Any = None,
    pay_method_arg: Any = None,
    operator_arg: Any = None,
    order_no_arg: Any = None,
) -> dict[str, Any]:
    from repositories import admin_booking_repository
    from utils.staff_booking import text_field
    status = _validate_status_filter(status_arg)
    username = text_field({'username':username_arg}, 'username', 50)
    operator = text_field({'operator':operator_arg}, 'operator', 50)
    order_no = text_field({'order_no':order_no_arg}, 'order_no', 64)
    source = text_field({'source':source_arg}, 'source', 30)
    pay_method = text_field({'pay_method':pay_method_arg}, 'pay_method', 20)
    if source and source not in ('online','walk_in','walk_in_extension'):
        raise ApiError(400, '预约来源参数不合法', 400)
    if pay_method and pay_method not in ('balance','mock_alipay'):
        raise ApiError(400, '支付渠道参数不合法', 400)
    if type(page) is not int or type(page_size) is not int or page<1 or not 1<=page_size<=100:
        raise ApiError(400, '分页参数不合法', 400)
    court_id = _parse_optional_int(court_id_arg, "场地ID")
    date_from = _parse_optional_date(date_from_arg, "开始日期")
    date_to = _parse_optional_date(date_to_arg, "结束日期")
    if date_from and date_to and date_from > date_to:
        raise ApiError(400, "开始日期不能晚于结束日期", 400)
    await refresh_reservation_statuses(settings)
    return await admin_booking_repository.list_page(settings, {
        'status':status,'username':username,'court_id':court_id,'date_from':date_from,'date_to':date_to,
        'source':source,'pay_method':pay_method,'operator':operator,'order_no':order_no,
    }, page=page,page_size=page_size)


async def get_admin_reservation(settings: Settings, reservation_id: int) -> dict[str, Any]:
    from repositories import admin_booking_repository
    await refresh_reservation_statuses(settings)
    return await admin_booking_repository.detail(settings, reservation_id)


async def admin_cancel_reservation(
    settings: Settings,
    reservation_id: int,
    *,
    current_user: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    await refresh_reservation_statuses(settings)
    reservation = await reservation_repository.get_reservation_detail(settings, reservation_id)
    if reservation is None:
        raise ApiError(404, "预约记录不存在", 404)
    if reservation.get('source') in ('walk_in','walk_in_extension'):
        from services import staff_booking_service
        # The compatibility endpoint cannot issue a wallet credit for a guest.
        if not current_user:
            raise ApiError(403, '需要管理员身份', 403)
        payload = body or {}
        payload.setdefault('request_key', f'admin-cancel-{reservation_id}')
        payload.setdefault('reason','管理员取消散客订场')
        action = 'cancel' if reservation['status']=='pending' or not reservation.get('order_paid_at') else 'refund'
        result = await staff_booking_service.action(settings,current_user,reservation_id,action,payload)
        updated = await reservation_repository.get_reservation_detail(settings,reservation_id)
        result.update(_normalize_reservation(updated))
        result['refund_cents'] = result['payment']['amount_cents'] if action=='refund' else 0
        return result
    from repositories import customer_booking_repository as online
    from utils.staff_booking import request_key, text_field
    payment=await online.initial_payment(settings,reservation_id)
    if payment:
        if not current_user: raise ApiError(403,'需要管理员身份',403)
        payload=body or {}
        key=request_key(payload) if 'request_key' in payload else f'admin-cancel-{reservation_id}'
        return await online.cancel(settings,current_user,await online.link(settings,payment['id']),key,
            text_field(payload,'reason',255) or '管理员取消预约',by_admin=True)
    if reservation["status"] == "canceled":
        raise ApiError(400, "预约已取消", 400)
    if reservation["status"] in {"completed", "expired"}:
        raise ApiError(400, "当前预约状态不能取消", 400)
    _canceled_id, failure_reason, refund_cents = await reservation_repository.cancel_reservation_atomic(
        settings,
        reservation_id,
        operator_id=current_user.get("id") if current_user else None,
        operator_username=current_user.get("username") if current_user else None,
        reason="管理员取消预约" if reservation["status"] == "pending" else "管理员取消预约退款",
    )
    if failure_reason == "not_found":
        raise ApiError(404, "预约记录不存在", 404)
    if failure_reason in {"attendance_recorded", "already_started"}:
        raise ApiError(409, "预约已到场或已开始，不能取消", 409)
    if failure_reason == "not_confirmed":
        raise ApiError(400, "当前预约状态不能取消", 400)
    updated = await reservation_repository.get_reservation_detail(settings, reservation_id)
    if updated is None:
        raise ApiError(404, "预约记录不存在", 404)
    normalized = _normalize_reservation(updated)
    normalized["refund_cents"] = refund_cents
    await notification_service.notify_reservation_canceled(
        settings,
        reservation=normalized,
        by_admin=True,
        operator_id=current_user.get("id") if current_user else None,
    )
    return normalized
