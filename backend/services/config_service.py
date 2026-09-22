from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

from config.settings import Settings
from repositories import config_repository
from utils.query import clean_text
from utils.response import ApiError


DEFAULT_CONFIGS = {
    "business_start_time": "09:00",
    "business_end_time": "21:00",
    "slot_interval_minutes": "60",
    "advance_reservation_days": "7",
    "daily_reservation_limit": "3",
    "max_reservation_hours": "2",
    "reservation_lock_ttl_seconds": "300",
    "reservation_payment_timeout_minutes": "15",
}

INTEGER_KEYS = {
    "slot_interval_minutes",
    "advance_reservation_days",
    "daily_reservation_limit",
    "max_reservation_hours",
    "reservation_lock_ttl_seconds",
    "reservation_payment_timeout_minutes",
}

TIME_KEYS = {"business_start_time", "business_end_time"}


@dataclass(frozen=True)
class ReservationRules:
    business_start_time: time
    business_end_time: time
    slot_interval_minutes: int
    advance_reservation_days: int
    daily_reservation_limit: int
    max_reservation_hours: int
    reservation_lock_ttl_seconds: int
    reservation_payment_timeout_minutes: int


def parse_time_value(value: str) -> time:
    try:
        hour, minute = value.split(":")
        return time(hour=int(hour), minute=int(minute))
    except Exception as exc:
        raise ApiError(400, "时间配置格式应为 HH:MM", 400) from exc


def validate_config_value(config_key: str, config_value: str) -> str:
    value = clean_text(config_value)
    if config_key in TIME_KEYS:
        parse_time_value(value)
        return value
    if config_key in INTEGER_KEYS:
        try:
            number = int(value)
        except ValueError as exc:
            raise ApiError(400, "配置值必须是正整数", 400) from exc
        if number <= 0:
            raise ApiError(400, "配置值必须是正整数", 400)
        return str(number)
    if not value:
        raise ApiError(400, "配置值不能为空", 400)
    return value


async def get_config_map(settings: Settings) -> dict[str, str]:
    rows = await config_repository.list_configs(settings)
    values = DEFAULT_CONFIGS.copy()
    values.update({row["config_key"]: row["config_value"] for row in rows})
    return values


async def get_reservation_rules(settings: Settings) -> ReservationRules:
    config_map = await get_config_map(settings)
    start_time = parse_time_value(config_map["business_start_time"])
    end_time = parse_time_value(config_map["business_end_time"])
    if start_time >= end_time:
        raise ApiError(500, "营业结束时间必须晚于开始时间", 500)
    return ReservationRules(
        business_start_time=start_time,
        business_end_time=end_time,
        slot_interval_minutes=int(config_map["slot_interval_minutes"]),
        advance_reservation_days=int(config_map["advance_reservation_days"]),
        daily_reservation_limit=int(config_map["daily_reservation_limit"]),
        max_reservation_hours=int(config_map["max_reservation_hours"]),
        reservation_lock_ttl_seconds=int(config_map["reservation_lock_ttl_seconds"]),
        reservation_payment_timeout_minutes=int(config_map["reservation_payment_timeout_minutes"]),
    )


async def list_configs(settings: Settings) -> list[dict[str, Any]]:
    return await config_repository.list_configs(settings)


async def public_reservation_rules(settings: Settings) -> dict[str, Any]:
    rules = await get_reservation_rules(settings)
    today = date.today()
    return {
        "business_start_time": rules.business_start_time.strftime("%H:%M"),
        "business_end_time": rules.business_end_time.strftime("%H:%M"),
        "slot_interval_minutes": rules.slot_interval_minutes,
        "max_reservation_minutes": rules.max_reservation_hours * 60,
        "daily_reservation_limit": rules.daily_reservation_limit,
        "payment_timeout_minutes": rules.reservation_payment_timeout_minutes,
        "min_date": today.isoformat(),
        "max_date": (today + timedelta(days=rules.advance_reservation_days)).isoformat(),
        "server_now": datetime.now().astimezone().isoformat(),
    }


async def update_config(
    settings: Settings,
    *,
    config_key: str,
    config_value: str,
    updated_by: int,
) -> dict[str, Any]:
    existing = await config_repository.get_config(settings, config_key)
    if existing is None:
        raise ApiError(404, "配置项不存在", 404)
    validated_value = validate_config_value(config_key, config_value)
    await config_repository.update_config(
        settings,
        config_key=config_key,
        config_value=validated_value,
        updated_by=updated_by,
    )
    updated = await config_repository.get_config(settings, config_key)
    if updated is None:
        raise ApiError(404, "配置项不存在", 404)
    return updated
