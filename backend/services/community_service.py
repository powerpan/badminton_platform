from typing import Any

from config.settings import Settings
from repositories import community_repository
from utils.query import clean_text
from utils.response import ApiError


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


def _normalize_post(row: dict[str, Any]) -> dict[str, Any]:
    post = dict(row)
    post["status"] = int(post.get("status") or 0)
    return post


async def list_public_posts(
    settings: Settings,
    *,
    page: int,
    page_size: int,
    offset: int,
) -> dict[str, Any]:
    rows = await community_repository.list_posts(settings, status=1, offset=offset, limit=page_size)
    total = await community_repository.count_posts(settings, status=1)
    return {"items": [_normalize_post(row) for row in rows], "total": total, "page": page, "page_size": page_size}


async def create_post(
    settings: Settings,
    *,
    current_user: dict[str, Any],
    body: dict[str, Any],
) -> dict[str, Any]:
    content = clean_text(body.get("content"))
    if not content:
        raise ApiError(400, "动态内容不能为空", 400)
    if len(content) > 1000:
        raise ApiError(400, "动态内容不能超过1000个字符", 400)
    post_id = await community_repository.create_post(settings, user_id=current_user["id"], content=content)
    post = await community_repository.get_post(settings, post_id)
    if post is None:
        raise ApiError(500, "发布动态后读取失败", 500)
    return _normalize_post(post)


async def hide_own_post(settings: Settings, *, current_user: dict[str, Any], post_id: int) -> dict[str, Any]:
    post = await community_repository.get_post(settings, post_id)
    if post is None or int(post["user_id"]) != current_user["id"]:
        raise ApiError(404, "动态不存在", 404)
    if int(post["status"]) != 1:
        raise ApiError(400, "该动态已隐藏", 400)
    updated_count = await community_repository.hide_post(settings, post_id=post_id, user_id=current_user["id"])
    if updated_count <= 0:
        raise ApiError(404, "动态不存在", 404)
    updated = await community_repository.get_post(settings, post_id)
    if updated is None:
        raise ApiError(404, "动态不存在", 404)
    return _normalize_post(updated)


async def list_admin_posts(
    settings: Settings,
    *,
    status_arg: Any,
    page: int,
    page_size: int,
    offset: int,
) -> dict[str, Any]:
    status = _parse_status(status_arg, default=None)
    rows = await community_repository.list_posts(settings, status=status, offset=offset, limit=page_size)
    total = await community_repository.count_posts(settings, status=status)
    return {"items": [_normalize_post(row) for row in rows], "total": total, "page": page, "page_size": page_size}


async def admin_hide_post(settings: Settings, post_id: int) -> dict[str, Any]:
    post = await community_repository.get_post(settings, post_id)
    if post is None:
        raise ApiError(404, "动态不存在", 404)
    if int(post["status"]) != 1:
        raise ApiError(400, "该动态已隐藏", 400)
    updated_count = await community_repository.hide_post(settings, post_id=post_id)
    if updated_count <= 0:
        raise ApiError(404, "动态不存在", 404)
    updated = await community_repository.get_post(settings, post_id)
    if updated is None:
        raise ApiError(404, "动态不存在", 404)
    return _normalize_post(updated)
