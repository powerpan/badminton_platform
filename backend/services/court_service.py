from datetime import date, datetime, timedelta, time
from typing import Any

from config.settings import Settings
from repositories import court_repository, reservation_repository
from services.config_service import get_reservation_rules
from services.redis_service import lock_exists, reservation_lock_key
from utils.query import clean_text
from utils.response import ApiError


def _to_time_string(value: Any) -> str:
    if isinstance(value, timedelta):
        total_seconds = int(value.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, _seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}"
    if isinstance(value, time):
        return value.strftime("%H:%M")
    text = str(value)
    return text[:5]


def _parse_status(value: Any, default: int | None = None) -> int | None:
    if value is None or value == "":
        return default
    try:
        status = int(value)
    except (TypeError, ValueError) as exc:
        raise ApiError(400, "状态参数格式错误", 400) from exc
    if status not in (0, 1):
        raise ApiError(400, "状态只能是0或1", 400)
    return status


def _parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ApiError(400, "日期格式应为 YYYY-MM-DD", 400) from exc


async def list_courts(
    settings: Settings,
    *,
    status_arg: Any,
    page: int,
    page_size: int,
    offset: int,
) -> dict[str, Any]:
    status = _parse_status(status_arg, default=1)
    rows = await court_repository.list_courts(settings, status=status, offset=offset, limit=page_size)
    total = await court_repository.count_courts(settings, status=status)
    return {"items": rows, "total": total, "page": page, "page_size": page_size}


async def list_admin_courts(
    settings: Settings,
    *,
    status_arg: Any,
    page: int,
    page_size: int,
    offset: int,
) -> dict[str, Any]:
    status = _parse_status(status_arg, default=None)
    rows = await court_repository.list_courts(settings, status=status, offset=offset, limit=page_size)
    total = await court_repository.count_courts(settings, status=status)
    return {"items": rows, "total": total, "page": page, "page_size": page_size}


async def get_slots(settings: Settings, *, court_id: int, date_arg: str) -> dict[str, Any]:
    reserve_date = _parse_date(date_arg)
    court = await court_repository.get_court_by_id(settings, court_id)
    if court is None:
        raise ApiError(404, "场地不存在", 404)

    rules = await get_reservation_rules(settings)
    existing_reservations = await reservation_repository.list_reservations_for_court_date(
        settings,
        court_id=court_id,
        reserve_date=reserve_date,
    )
    reserved_slots = {
        (_to_time_string(row["start_time"]), _to_time_string(row["end_time"]))
        for row in existing_reservations
    }

    slots = []
    current_dt = datetime.combine(reserve_date, rules.business_start_time)
    end_dt = datetime.combine(reserve_date, rules.business_end_time)
    now = datetime.now()
    latest_date = date.today() + timedelta(days=rules.advance_reservation_days)
    date_out_of_range = reserve_date < date.today() or reserve_date > latest_date

    while current_dt < end_dt:
        next_dt = current_dt + timedelta(minutes=rules.slot_interval_minutes)
        if next_dt > end_dt:
            break
        start_text = current_dt.strftime("%H:%M")
        end_text = next_dt.strftime("%H:%M")
        status = "available"
        if court["status"] != 1 or date_out_of_range or current_dt <= now:
            status = "disabled"
        elif (start_text, end_text) in reserved_slots:
            status = "reserved"
        else:
            key = reservation_lock_key(court_id, reserve_date.isoformat(), start_text, end_text)
            if await lock_exists(settings, key):
                status = "locked"
        slots.append({"start_time": start_text, "end_time": end_text, "status": status})
        current_dt = next_dt

    return {"court_id": court_id, "court": court, "date": reserve_date.isoformat(), "slots": slots}


async def create_court(settings: Settings, body: dict[str, Any]) -> dict[str, Any]:
    court_no = clean_text(body.get("court_no"))
    court_name = clean_text(body.get("court_name"))
    description = clean_text(body.get("description"))
    status = _parse_status(body.get("status"), default=1)
    if not court_no:
        raise ApiError(400, "场地编号不能为空", 400)
    if not court_name:
        raise ApiError(400, "场地名称不能为空", 400)
    if await court_repository.get_court_by_no(settings, court_no):
        raise ApiError(409, "场地编号已存在", 409)
    court_id = await court_repository.create_court(
        settings,
        court_no=court_no,
        court_name=court_name,
        description=description,
        status=status if status is not None else 1,
    )
    court = await court_repository.get_court_by_id(settings, court_id)
    if court is None:
        raise ApiError(500, "创建场地后读取失败", 500)
    return court


async def update_court(settings: Settings, court_id: int, body: dict[str, Any]) -> dict[str, Any]:
    court = await court_repository.get_court_by_id(settings, court_id)
    if court is None:
        raise ApiError(404, "场地不存在", 404)
    court_no = clean_text(body.get("court_no"))
    court_name = clean_text(body.get("court_name"))
    description = clean_text(body.get("description"))
    status = _parse_status(body.get("status"), default=int(court["status"]))
    if not court_no:
        raise ApiError(400, "场地编号不能为空", 400)
    if not court_name:
        raise ApiError(400, "场地名称不能为空", 400)
    existing = await court_repository.get_court_by_no(settings, court_no)
    if existing and existing["id"] != court_id:
        raise ApiError(409, "场地编号已存在", 409)
    if status == 0:
        future_count = await reservation_repository.count_future_active_reservations_by_court(settings, court_id=court_id)
        if future_count > 0:
            raise ApiError(409, f"该场地还有 {future_count} 条未来预约，请先取消预约后再停用", 409)
    await court_repository.update_court(
        settings,
        court_id=court_id,
        court_no=court_no,
        court_name=court_name,
        description=description,
        status=status or 0,
    )
    updated = await court_repository.get_court_by_id(settings, court_id)
    if updated is None:
        raise ApiError(404, "场地不存在", 404)
    return updated


async def update_court_status(settings: Settings, court_id: int, body: dict[str, Any]) -> dict[str, Any]:
    status = _parse_status(body.get("status"), default=None)
    if status is None:
        raise ApiError(400, "状态不能为空", 400)
    if await court_repository.get_court_by_id(settings, court_id) is None:
        raise ApiError(404, "场地不存在", 404)
    if status == 0:
        future_count = await reservation_repository.count_future_active_reservations_by_court(settings, court_id=court_id)
        if future_count > 0:
            raise ApiError(409, f"该场地还有 {future_count} 条未来预约，请先取消预约后再停用", 409)
    await court_repository.update_court_status(settings, court_id, status)
    updated = await court_repository.get_court_by_id(settings, court_id)
    if updated is None:
        raise ApiError(404, "场地不存在", 404)
    return updated
