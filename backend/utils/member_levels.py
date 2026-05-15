from datetime import date, datetime, timedelta
from typing import Any


MEMBER_LEVELS = {
    "normal": {"label": "普通会员", "discount_rate": 100},
    "silver": {"label": "银卡会员", "discount_rate": 95},
    "gold": {"label": "金卡会员", "discount_rate": 90},
    "diamond": {"label": "钻石会员", "discount_rate": 85},
}

DEFAULT_MEMBER_LEVEL = "normal"


def valid_member_level(value: Any) -> str:
    level = str(value or DEFAULT_MEMBER_LEVEL).strip() or DEFAULT_MEMBER_LEVEL
    if level not in MEMBER_LEVELS:
        raise ValueError("invalid member level")
    return level


def _to_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, timedelta):
        return (datetime.min + value).date()
    return datetime.strptime(str(value), "%Y-%m-%d").date()


def is_member_active(expires_at: Any, target_date: date | None = None) -> bool:
    expires_date = _to_date(expires_at)
    if expires_date is None:
        return True
    return (target_date or date.today()) <= expires_date


def effective_member_level(level: Any, expires_at: Any, target_date: date | None = None) -> str:
    member_level = valid_member_level(level)
    if member_level == DEFAULT_MEMBER_LEVEL or is_member_active(expires_at, target_date):
        return member_level
    return DEFAULT_MEMBER_LEVEL


def discount_rate_for_level(level: Any) -> int:
    return int(MEMBER_LEVELS[valid_member_level(level)]["discount_rate"])


def member_level_label(level: Any) -> str:
    return str(MEMBER_LEVELS[valid_member_level(level)]["label"])


def public_member(account: dict[str, Any] | None, *, target_date: date | None = None) -> dict[str, Any]:
    account = account or {}
    level = valid_member_level(account.get("member_level"))
    effective_level = effective_member_level(level, account.get("expires_at"), target_date)
    expires_at = _to_date(account.get("expires_at"))
    return {
        "level": level,
        "level_label": member_level_label(level),
        "balance_cents": int(account.get("balance_cents") or 0),
        "points": int(account.get("points") or 0),
        "expires_at": expires_at.isoformat() if expires_at else None,
        "discount_rate": discount_rate_for_level(level),
        "effective_level": effective_level,
        "effective_discount_rate": discount_rate_for_level(effective_level),
    }
