from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from config.settings import Settings
from repositories import statistics_repository
from services.config_service import get_reservation_rules
from services.reservation_service import refresh_reservation_statuses
from utils.query import clean_text, to_int
from utils.response import ApiError


def _parse_date(value: Any, default: date) -> date:
    text = clean_text(value)
    if not text:
        return default
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ApiError(400, "统计日期格式应为 YYYY-MM-DD", 400) from exc


def _date_range(date_from_arg: Any, date_to_arg: Any) -> tuple[date, date]:
    today = date.today()
    date_from = _parse_date(date_from_arg, today)
    date_to = _parse_date(date_to_arg, today + timedelta(days=6))
    if date_from > date_to:
        raise ApiError(400, "开始日期不能晚于结束日期", 400)
    if (date_to - date_from).days > 366:
        raise ApiError(400, "统计日期范围不能超过366天", 400)
    return date_from, date_to


def _as_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _time_minutes(value: Any) -> int:
    return value.hour * 60 + value.minute


def _time_text(value: Any) -> str:
    if isinstance(value, timedelta):
        total_seconds = int(value.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, _seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}"
    if isinstance(value, time):
        return value.strftime("%H:%M")
    return str(value)[:5]


def _status_count(counts: dict[str, int], status: str) -> int:
    return int(counts.get(status, 0))


async def get_overview(
    settings: Settings,
    *,
    date_from_arg: Any,
    date_to_arg: Any,
) -> dict[str, Any]:
    await refresh_reservation_statuses(settings)
    date_from, date_to = _date_range(date_from_arg, date_to_arg)
    user_counts = await statistics_repository.get_user_counts(settings)
    court_counts = await statistics_repository.get_court_counts(settings)
    reservation_counts = await statistics_repository.get_reservation_status_counts(
        settings,
        date_from=date_from,
        date_to=date_to,
    )
    today_reservations = await statistics_repository.count_today_reservations(settings)
    active_users = await statistics_repository.count_active_users(settings, date_from=date_from, date_to=date_to)
    rules = await get_reservation_rules(settings)

    day_count = (date_to - date_from).days + 1
    business_minutes = _time_minutes(rules.business_end_time) - _time_minutes(rules.business_start_time)
    slots_per_day = max(0, business_minutes // rules.slot_interval_minutes)
    capacity_slots = court_counts["enabled_courts"] * day_count * slots_per_day
    occupied_slots = (
        _status_count(reservation_counts, "pending")
        + _status_count(reservation_counts, "confirmed")
        + _status_count(reservation_counts, "completed")
    )
    utilization_rate = round((occupied_slots / capacity_slots) * 100, 2) if capacity_slots else 0

    return {
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "total_users": user_counts["total_users"],
        "enabled_users": user_counts["enabled_users"],
        "admin_users": user_counts["admin_users"],
        "total_courts": court_counts["total_courts"],
        "enabled_courts": court_counts["enabled_courts"],
        "reservation_total": reservation_counts["total"],
        "today_reservations": today_reservations,
        "active_users": active_users,
        "pending_reservations": _status_count(reservation_counts, "pending"),
        "confirmed_reservations": _status_count(reservation_counts, "confirmed"),
        "completed_reservations": _status_count(reservation_counts, "completed"),
        "canceled_reservations": _status_count(reservation_counts, "canceled"),
        "expired_reservations": _status_count(reservation_counts, "expired"),
        "capacity_slots": capacity_slots,
        "occupied_slots": occupied_slots,
        "utilization_rate": utilization_rate,
    }


async def list_court_statistics(
    settings: Settings,
    *,
    date_from_arg: Any,
    date_to_arg: Any,
) -> dict[str, Any]:
    await refresh_reservation_statuses(settings)
    date_from, date_to = _date_range(date_from_arg, date_to_arg)
    rules = await get_reservation_rules(settings)
    day_count = (date_to - date_from).days + 1
    business_minutes = _time_minutes(rules.business_end_time) - _time_minutes(rules.business_start_time)
    slots_per_day = max(0, business_minutes // rules.slot_interval_minutes)
    capacity_slots = day_count * slots_per_day
    rows = await statistics_repository.list_court_usage(settings, date_from=date_from, date_to=date_to)
    items = []
    for row in rows:
        active_count = int(row["active_count"] or 0)
        court_capacity = capacity_slots if int(row["status"]) == 1 else 0
        items.append(
            {
                "court_id": row["id"],
                "court_no": row["court_no"],
                "court_name": row["court_name"],
                "status": row["status"],
                "reservation_count": int(row["reservation_count"] or 0),
                "active_count": active_count,
                "booked_hours": round(_as_float(row["booked_hours"]), 2),
                "capacity_slots": court_capacity,
                "usage_rate": round((active_count / court_capacity) * 100, 2) if court_capacity else 0,
            }
        )
    return {"date_from": date_from.isoformat(), "date_to": date_to.isoformat(), "items": items}


async def list_time_slot_statistics(
    settings: Settings,
    *,
    date_from_arg: Any,
    date_to_arg: Any,
    limit_arg: Any,
) -> dict[str, Any]:
    await refresh_reservation_statuses(settings)
    date_from, date_to = _date_range(date_from_arg, date_to_arg)
    limit = to_int(limit_arg, 12, min_value=1, max_value=24)
    rows = await statistics_repository.list_time_slot_usage(
        settings,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )
    return {
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "items": [
            {
                "time_slot": row["time_slot"],
                "start_time": _time_text(row["start_time"]),
                "end_time": _time_text(row["end_time"]),
                "reservation_count": int(row["reservation_count"] or 0),
            }
            for row in rows
        ],
    }


async def list_user_statistics(
    settings: Settings,
    *,
    date_from_arg: Any,
    date_to_arg: Any,
    limit_arg: Any,
) -> dict[str, Any]:
    await refresh_reservation_statuses(settings)
    date_from, date_to = _date_range(date_from_arg, date_to_arg)
    limit = to_int(limit_arg, 10, min_value=1, max_value=50)
    rows = await statistics_repository.list_user_activity(
        settings,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )
    return {
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "items": [
            {
                "user_id": row["user_id"],
                "username": row["username"],
                "nickname": row["nickname"],
                "reservation_count": int(row["reservation_count"] or 0),
                "confirmed_count": int(row["confirmed_count"] or 0),
                "completed_count": int(row["completed_count"] or 0),
                "canceled_count": int(row["canceled_count"] or 0),
                "last_reserve_date": row["last_reserve_date"],
            }
            for row in rows
        ],
    }
