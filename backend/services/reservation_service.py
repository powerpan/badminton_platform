import time as time_module
from datetime import date, datetime, time, timedelta
from typing import Any

from config.settings import Settings
from repositories import court_repository, reservation_repository
from services.config_service import get_reservation_rules
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
    return "R" + datetime.now().strftime("%Y%m%d%H%M%S") + str(int(time_module.time() * 1000) % 1000).zfill(3)


def _normalize_reservation(row: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(row)
    if "start_time" in normalized:
        normalized["start_time"] = _time_text(normalized["start_time"])
    if "end_time" in normalized:
        normalized["end_time"] = _time_text(normalized["end_time"])
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
    return await reservation_repository.complete_finished_reservations(settings)


async def create_reservation(
    settings: Settings,
    *,
    current_user: dict[str, Any],
    body: dict[str, Any],
) -> dict[str, Any]:
    await refresh_reservation_statuses(settings)
    try:
        court_id = int(body.get("court_id"))
    except (TypeError, ValueError) as exc:
        raise ApiError(400, "场地ID不能为空", 400) from exc
    reserve_date = _parse_date(body.get("reserve_date"))
    start_time = _parse_time(body.get("start_time"))
    end_time = _parse_time(body.get("end_time"))
    remark = clean_text(body.get("remark"))

    if end_time <= start_time:
        raise ApiError(400, "结束时间必须晚于开始时间", 400)

    now = datetime.now()
    start_dt = datetime.combine(reserve_date, start_time)
    end_dt = datetime.combine(reserve_date, end_time)
    if start_dt <= now:
        raise ApiError(400, "不能预约过去时间段", 400)

    rules = await get_reservation_rules(settings)
    latest_date = date.today() + timedelta(days=rules.advance_reservation_days)
    if reserve_date > latest_date:
        raise ApiError(400, "预约日期超过可提前预约范围", 400)
    if start_time < rules.business_start_time or end_time > rules.business_end_time:
        raise ApiError(400, "预约时间不在营业时间内", 400)
    start_offset = _minutes(start_time) - _minutes(rules.business_start_time)
    end_offset = _minutes(end_time) - _minutes(rules.business_start_time)
    if start_offset % rules.slot_interval_minutes != 0 or end_offset % rules.slot_interval_minutes != 0:
        raise ApiError(400, "预约时间必须按系统时间段选择", 400)
    max_minutes = rules.max_reservation_hours * 60
    if int((end_dt - start_dt).total_seconds() // 60) > max_minutes:
        raise ApiError(400, "预约时长超过系统限制", 400)

    court = await court_repository.get_court_by_id(settings, court_id)
    if court is None:
        raise ApiError(404, "场地不存在", 404)
    if court["status"] != 1:
        raise ApiError(400, "场地已停用，不能预约", 400)

    start_text = start_time.strftime("%H:%M")
    end_text = end_time.strftime("%H:%M")
    lock_key = reservation_lock_key(court_id, reserve_date.isoformat(), start_text, end_text)
    lock_value = f"{current_user['id']}:{time_module.time_ns()}"
    locked = await acquire_lock(settings, lock_key, lock_value, rules.reservation_lock_ttl_seconds)
    if not locked:
        raise ApiError(409, "该时间段正在预约或已被占用", 409)

    try:
        reservation_id, failure_reason = await reservation_repository.create_confirmed_reservation_atomic(
            settings,
            reservation_no=_reservation_no(),
            user_id=current_user["id"],
            court_id=court_id,
            reserve_date=reserve_date,
            start_time=start_time,
            end_time=end_time,
            time_slot=f"{start_text}-{end_text}",
            remark=remark,
            daily_limit=rules.daily_reservation_limit,
        )
        if failure_reason == "conflict":
            raise ApiError(409, "该时间段已被预约", 409)
        if failure_reason == "daily_limit":
            raise ApiError(400, "当天预约次数已达上限", 400)
        if failure_reason == "insufficient_balance":
            raise ApiError(400, "会员余额不足，请联系管理员充值或调整余额", 400)
        if failure_reason == "court_not_found":
            raise ApiError(404, "场地不存在", 404)
        if failure_reason == "court_disabled":
            raise ApiError(400, "场地已停用，不能预约", 400)
        if failure_reason == "user_not_found":
            raise ApiError(401, "登录用户不存在，请重新登录", 401)
        if failure_reason == "user_disabled":
            raise ApiError(403, "账号已被禁用", 403)
        if reservation_id is None:
            raise ApiError(409, "预约提交失败，请重试", 409)

        detail = await reservation_repository.get_reservation_detail(settings, reservation_id)
        if detail is None:
            raise ApiError(500, "预约成功但读取记录失败", 500)
        return _normalize_reservation(detail)
    finally:
        await release_lock(settings, lock_key, lock_value)


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
) -> dict[str, Any]:
    await refresh_reservation_statuses(settings)
    reservation = await reservation_repository.get_reservation_detail(settings, reservation_id)
    if reservation is None or reservation["user_id"] != current_user["id"]:
        raise ApiError(404, "预约记录不存在", 404)
    if reservation["status"] != "confirmed":
        raise ApiError(400, "当前预约状态不能取消", 400)
    reserve_date = reservation["reserve_date"]
    start_time = reservation["start_time"]
    start_dt = datetime.combine(reserve_date, start_time if isinstance(start_time, time) else (datetime.min + start_time).time())
    if start_dt <= datetime.now():
        raise ApiError(400, "已开始或已过期的预约不能取消", 400)
    _canceled_id, failure_reason = await reservation_repository.cancel_reservation_atomic(
        settings,
        reservation_id,
        operator_id=current_user.get("id"),
        operator_username=current_user.get("username"),
        reason="用户取消预约退款",
    )
    if failure_reason == "not_found":
        raise ApiError(404, "预约记录不存在", 404)
    if failure_reason == "not_confirmed":
        raise ApiError(400, "当前预约状态不能取消", 400)
    updated = await reservation_repository.get_reservation_detail(settings, reservation_id)
    if updated is None:
        raise ApiError(404, "预约记录不存在", 404)
    return _normalize_reservation(updated)


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
) -> dict[str, Any]:
    await refresh_reservation_statuses(settings)
    status = _validate_status_filter(status_arg)
    username = clean_text(username_arg)
    court_id = _parse_optional_int(court_id_arg, "场地ID")
    date_from = _parse_optional_date(date_from_arg, "开始日期")
    date_to = _parse_optional_date(date_to_arg, "结束日期")
    if date_from and date_to and date_from > date_to:
        raise ApiError(400, "开始日期不能晚于结束日期", 400)
    rows = await reservation_repository.list_admin_reservations(
        settings,
        status=status,
        username=username or None,
        court_id=court_id,
        date_from=date_from,
        date_to=date_to,
        offset=offset,
        limit=page_size,
    )
    total = await reservation_repository.count_admin_reservations_filtered(
        settings,
        status=status,
        username=username or None,
        court_id=court_id,
        date_from=date_from,
        date_to=date_to,
    )
    return {"items": [_normalize_reservation(row) for row in rows], "total": total, "page": page, "page_size": page_size}


async def get_admin_reservation(settings: Settings, reservation_id: int) -> dict[str, Any]:
    await refresh_reservation_statuses(settings)
    reservation = await reservation_repository.get_reservation_detail(settings, reservation_id)
    if reservation is None:
        raise ApiError(404, "预约记录不存在", 404)
    return _normalize_reservation(reservation)


async def admin_cancel_reservation(
    settings: Settings,
    reservation_id: int,
    *,
    current_user: dict[str, Any] | None = None,
) -> dict[str, Any]:
    await refresh_reservation_statuses(settings)
    reservation = await reservation_repository.get_reservation_detail(settings, reservation_id)
    if reservation is None:
        raise ApiError(404, "预约记录不存在", 404)
    if reservation["status"] == "canceled":
        raise ApiError(400, "预约已取消", 400)
    if reservation["status"] in {"completed", "expired"}:
        raise ApiError(400, "当前预约状态不能取消", 400)
    _canceled_id, failure_reason = await reservation_repository.cancel_reservation_atomic(
        settings,
        reservation_id,
        operator_id=current_user.get("id") if current_user else None,
        operator_username=current_user.get("username") if current_user else None,
        reason="管理员取消预约退款",
    )
    if failure_reason == "not_found":
        raise ApiError(404, "预约记录不存在", 404)
    if failure_reason == "not_confirmed":
        raise ApiError(400, "当前预约状态不能取消", 400)
    updated = await reservation_repository.get_reservation_detail(settings, reservation_id)
    if updated is None:
        raise ApiError(404, "预约记录不存在", 404)
    return _normalize_reservation(updated)
