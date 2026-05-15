from typing import Any

from config.settings import Settings
from repositories import announcement_repository
from utils.query import clean_text
from utils.response import ApiError


def _parse_status(value: Any, *, default: int | None = None) -> int | None:
    if value is None or value == "":
        return default
    try:
        status = int(value)
    except (TypeError, ValueError) as exc:
        raise ApiError(400, "公告状态格式错误", 400) from exc
    if status not in (0, 1):
        raise ApiError(400, "公告状态只能是0或1", 400)
    return status


def _validate_content(title: str, content: str) -> None:
    if not title:
        raise ApiError(400, "公告标题不能为空", 400)
    if len(title) > 100:
        raise ApiError(400, "公告标题不能超过100个字符", 400)
    if not content:
        raise ApiError(400, "公告内容不能为空", 400)


async def list_public_announcements(
    settings: Settings,
    *,
    page: int,
    page_size: int,
    offset: int,
) -> dict[str, Any]:
    rows = await announcement_repository.list_announcements(settings, status=1, offset=offset, limit=page_size)
    total = await announcement_repository.count_announcements(settings, status=1)
    return {"items": rows, "total": total, "page": page, "page_size": page_size}


async def get_public_announcement(settings: Settings, announcement_id: int) -> dict[str, Any]:
    announcement = await announcement_repository.get_announcement(settings, announcement_id)
    if announcement is None or announcement["status"] != 1:
        raise ApiError(404, "公告不存在", 404)
    return announcement


async def list_admin_announcements(
    settings: Settings,
    *,
    status_arg: Any,
    page: int,
    page_size: int,
    offset: int,
) -> dict[str, Any]:
    status = _parse_status(status_arg, default=None)
    rows = await announcement_repository.list_announcements(settings, status=status, offset=offset, limit=page_size)
    total = await announcement_repository.count_announcements(settings, status=status)
    return {"items": rows, "total": total, "page": page, "page_size": page_size}


async def create_announcement(
    settings: Settings,
    *,
    current_user: dict[str, Any],
    body: dict[str, Any],
) -> dict[str, Any]:
    title = clean_text(body.get("title"))
    content = clean_text(body.get("content"))
    status = _parse_status(body.get("status"), default=1)
    _validate_content(title, content)
    announcement_id = await announcement_repository.create_announcement(
        settings,
        title=title,
        content=content,
        status=status if status is not None else 1,
        created_by=current_user["id"],
    )
    announcement = await announcement_repository.get_announcement(settings, announcement_id)
    if announcement is None:
        raise ApiError(500, "创建公告后读取失败", 500)
    return announcement


async def update_announcement(settings: Settings, announcement_id: int, body: dict[str, Any]) -> dict[str, Any]:
    announcement = await announcement_repository.get_announcement(settings, announcement_id)
    if announcement is None:
        raise ApiError(404, "公告不存在", 404)
    title = clean_text(body.get("title"))
    content = clean_text(body.get("content"))
    status = _parse_status(body.get("status"), default=int(announcement["status"]))
    _validate_content(title, content)
    await announcement_repository.update_announcement(
        settings,
        announcement_id=announcement_id,
        title=title,
        content=content,
        status=status if status is not None else 1,
    )
    updated = await announcement_repository.get_announcement(settings, announcement_id)
    if updated is None:
        raise ApiError(404, "公告不存在", 404)
    return updated


async def update_announcement_status(settings: Settings, announcement_id: int, body: dict[str, Any]) -> dict[str, Any]:
    status = _parse_status(body.get("status"))
    if await announcement_repository.get_announcement(settings, announcement_id) is None:
        raise ApiError(404, "公告不存在", 404)
    await announcement_repository.update_announcement_status(
        settings,
        announcement_id,
        status if status is not None else 0,
    )
    updated = await announcement_repository.get_announcement(settings, announcement_id)
    if updated is None:
        raise ApiError(404, "公告不存在", 404)
    return updated
