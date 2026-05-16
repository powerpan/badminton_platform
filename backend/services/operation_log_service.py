import json
from datetime import datetime, timedelta
from typing import Any

from config.settings import Settings
from repositories import operation_log_repository
from utils.query import clean_text
from utils.response import ApiError


VALID_MODULES = {"user", "court", "reservation", "announcement", "notification", "config", "shop", "event", "community"}
VALID_ACTIONS = {"create", "update", "status", "role", "member", "cancel", "hide", "broadcast", "complete"}


def _parse_date_arg(value: Any, field_name: str) -> datetime | None:
    text = clean_text(value)
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d")
    except ValueError as exc:
        raise ApiError(400, f"{field_name}格式应为 YYYY-MM-DD", 400) from exc


def _validate_filter(value: Any, allowed: set[str], message: str) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    if text not in allowed:
        raise ApiError(400, message, 400)
    return text


async def record_admin_operation(
    settings: Settings,
    *,
    current_user: dict[str, Any],
    module: str,
    action: str,
    target_type: str | None,
    target_id: int | None,
    detail: dict[str, Any] | None,
    ip: str | None,
) -> int:
    detail_text = json.dumps(detail or {}, ensure_ascii=False, default=str)
    return await operation_log_repository.create_operation_log(
        settings,
        user_id=current_user.get("id"),
        username=current_user.get("username"),
        role=current_user.get("role"),
        module=module,
        action=action,
        target_type=target_type,
        target_id=target_id,
        detail=detail_text,
        ip=ip,
    )


async def list_operation_logs(
    settings: Settings,
    *,
    module_arg: Any,
    action_arg: Any,
    username_arg: Any,
    date_from_arg: Any,
    date_to_arg: Any,
    page: int,
    page_size: int,
    offset: int,
) -> dict[str, Any]:
    module = _validate_filter(module_arg, VALID_MODULES, "日志模块参数不合法")
    action = _validate_filter(action_arg, VALID_ACTIONS, "日志操作参数不合法")
    username = clean_text(username_arg) or None
    start_at = _parse_date_arg(date_from_arg, "开始日期")
    end_at = _parse_date_arg(date_to_arg, "结束日期")
    if end_at:
        end_at = end_at + timedelta(days=1)
    if start_at and end_at and start_at >= end_at:
        raise ApiError(400, "开始日期不能晚于结束日期", 400)

    rows = await operation_log_repository.list_operation_logs(
        settings,
        module=module,
        action=action,
        username=username,
        start_at=start_at,
        end_at=end_at,
        offset=offset,
        limit=page_size,
    )
    total = await operation_log_repository.count_operation_logs(
        settings,
        module=module,
        action=action,
        username=username,
        start_at=start_at,
        end_at=end_at,
    )
    return {"items": rows, "total": total, "page": page, "page_size": page_size}
