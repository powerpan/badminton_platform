from datetime import datetime
from typing import Any

from config.settings import Settings
from repositories import event_repository
from services import notification_service
from utils.query import clean_text
from utils.response import ApiError


DATETIME_PATTERNS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M")


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


def _parse_datetime(value: Any, field_name: str) -> datetime:
    text = clean_text(value)
    for pattern in DATETIME_PATTERNS:
        try:
            return datetime.strptime(text, pattern)
        except ValueError:
            continue
    raise ApiError(400, f"{field_name}格式应为 YYYY-MM-DD HH:mm", 400)


def _parse_capacity(value: Any, default: int = 20) -> int:
    try:
        capacity = int(value if value not in (None, "") else default)
    except (TypeError, ValueError) as exc:
        raise ApiError(400, "活动容量格式错误", 400) from exc
    if capacity < 1 or capacity > 9999:
        raise ApiError(400, "活动容量范围应为 1-9999", 400)
    return capacity


def _normalize_event(row: dict[str, Any]) -> dict[str, Any]:
    event = dict(row)
    event["registered_count"] = int(event.get("registered_count") or 0)
    event["capacity"] = int(event.get("capacity") or 0)
    event["status"] = int(event.get("status") or 0)
    event["is_registered"] = bool(event.get("is_registered"))
    event["can_register"] = (
        event["status"] == 1
        and event["registered_count"] < event["capacity"]
        and event.get("registration_deadline") is not None
        and event["registration_deadline"] >= datetime.now()
        and not event["is_registered"]
    )
    return event


def _event_payload(body: dict[str, Any], *, existing: dict[str, Any] | None = None) -> dict[str, Any]:
    title = clean_text(body.get("title", existing.get("title") if existing else ""))
    content = clean_text(body.get("content", existing.get("content") if existing else ""))
    location = clean_text(body.get("location", existing.get("location") if existing else ""))
    start_at = _parse_datetime(body.get("start_at", existing.get("start_at") if existing else ""), "开始时间")
    end_at = _parse_datetime(body.get("end_at", existing.get("end_at") if existing else ""), "结束时间")
    registration_deadline = _parse_datetime(
        body.get("registration_deadline", existing.get("registration_deadline") if existing else ""),
        "报名截止时间",
    )
    capacity = _parse_capacity(body.get("capacity", existing.get("capacity") if existing else 20))
    status = _parse_status(body.get("status"), default=int(existing["status"]) if existing else 1)
    if not title:
        raise ApiError(400, "活动标题不能为空", 400)
    if len(title) > 100:
        raise ApiError(400, "活动标题不能超过100个字符", 400)
    if not content:
        raise ApiError(400, "活动内容不能为空", 400)
    if len(content) > 5000:
        raise ApiError(400, "活动内容不能超过5000个字符", 400)
    if not location:
        raise ApiError(400, "活动地点不能为空", 400)
    if end_at <= start_at:
        raise ApiError(400, "结束时间必须晚于开始时间", 400)
    if registration_deadline > start_at:
        raise ApiError(400, "报名截止时间不能晚于活动开始时间", 400)
    return {
        "title": title,
        "content": content,
        "location": location,
        "start_at": start_at,
        "end_at": end_at,
        "registration_deadline": registration_deadline,
        "capacity": capacity,
        "status": status if status is not None else 1,
    }


async def list_public_events(
    settings: Settings,
    *,
    user_id: int | None,
    page: int,
    page_size: int,
    offset: int,
) -> dict[str, Any]:
    rows = await event_repository.list_events(settings, status=1, user_id=user_id, offset=offset, limit=page_size)
    total = await event_repository.count_events(settings, status=1)
    return {"items": [_normalize_event(row) for row in rows], "total": total, "page": page, "page_size": page_size}


async def get_public_event(settings: Settings, event_id: int, *, user_id: int | None) -> dict[str, Any]:
    event = await event_repository.get_event(settings, event_id, user_id=user_id)
    if event is None or int(event["status"]) != 1:
        raise ApiError(404, "活动不存在", 404)
    return _normalize_event(event)


async def register_event(settings: Settings, *, current_user: dict[str, Any], event_id: int) -> dict[str, Any]:
    _ok, failure = await event_repository.register_event_atomic(settings, event_id=event_id, user_id=current_user["id"])
    if failure == "not_found":
        raise ApiError(404, "活动不存在", 404)
    if failure == "hidden":
        raise ApiError(400, "活动已隐藏，不能报名", 400)
    if failure == "deadline_passed":
        raise ApiError(400, "报名已截止", 400)
    if failure == "full":
        raise ApiError(400, "活动名额已满", 400)
    if failure == "already_registered":
        raise ApiError(400, "您已报名该活动", 400)
    if failure == "user_not_found":
        raise ApiError(401, "登录用户不存在，请重新登录", 401)
    if failure == "user_disabled":
        raise ApiError(403, "账号已被禁用", 403)
    event = await get_public_event(settings, event_id, user_id=current_user["id"])
    await notification_service.notify_event_registered(settings, event=event, user_id=current_user["id"])
    return event


async def cancel_registration(settings: Settings, *, current_user: dict[str, Any], event_id: int) -> dict[str, Any]:
    _ok, failure = await event_repository.cancel_registration_atomic(
        settings,
        event_id=event_id,
        user_id=current_user["id"],
    )
    if failure == "not_found":
        raise ApiError(404, "活动不存在", 404)
    if failure == "not_registered":
        raise ApiError(400, "您尚未报名该活动", 400)
    event = await get_public_event(settings, event_id, user_id=current_user["id"])
    await notification_service.notify_event_registration_canceled(settings, event=event, user_id=current_user["id"])
    return event


async def list_admin_events(
    settings: Settings,
    *,
    status_arg: Any,
    page: int,
    page_size: int,
    offset: int,
) -> dict[str, Any]:
    status = _parse_status(status_arg, default=None)
    rows = await event_repository.list_events(settings, status=status, user_id=None, offset=offset, limit=page_size)
    total = await event_repository.count_events(settings, status=status)
    return {"items": [_normalize_event(row) for row in rows], "total": total, "page": page, "page_size": page_size}


async def create_event(
    settings: Settings,
    *,
    current_user: dict[str, Any],
    body: dict[str, Any],
) -> dict[str, Any]:
    payload = _event_payload(body)
    event_id = await event_repository.create_event(settings, **payload, created_by=current_user["id"])
    event = await event_repository.get_event(settings, event_id)
    if event is None:
        raise ApiError(500, "创建活动后读取失败", 500)
    return _normalize_event(event)


async def update_event(settings: Settings, event_id: int, body: dict[str, Any]) -> dict[str, Any]:
    existing = await event_repository.get_event(settings, event_id)
    if existing is None:
        raise ApiError(404, "活动不存在", 404)
    payload = _event_payload(body, existing=existing)
    if payload["capacity"] < int(existing.get("registered_count") or 0):
        raise ApiError(400, "活动容量不能小于已报名人数", 400)
    await event_repository.update_event(settings, event_id=event_id, **payload)
    updated = await event_repository.get_event(settings, event_id)
    if updated is None:
        raise ApiError(404, "活动不存在", 404)
    return _normalize_event(updated)


async def update_event_status(
    settings: Settings,
    *,
    current_user: dict[str, Any],
    event_id: int,
    body: dict[str, Any],
) -> dict[str, Any]:
    event = await event_repository.get_event(settings, event_id)
    if event is None:
        raise ApiError(404, "活动不存在", 404)
    status = _parse_status(body.get("status"), default=None)
    if status is None:
        raise ApiError(400, "状态不能为空", 400)
    user_ids = await event_repository.list_active_registration_user_ids(settings, event_id) if status == 0 else []
    await event_repository.update_event_status(settings, event_id, status)
    updated = await event_repository.get_event(settings, event_id)
    if updated is None:
        raise ApiError(404, "活动不存在", 404)
    normalized = _normalize_event(updated)
    if status == 0 and int(event.get("status") or 0) == 1 and user_ids:
        await notification_service.notify_event_hidden(
            settings,
            event=normalized,
            user_ids=user_ids,
            operator_id=current_user["id"],
        )
    return normalized
