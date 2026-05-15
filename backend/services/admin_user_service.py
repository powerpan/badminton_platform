import asyncio
from datetime import date, datetime
from typing import Any

from config.settings import Settings
from repositories import member_repository, reservation_repository, user_repository
from services.auth_service import public_user, revoke_user_refresh_tokens
from utils.member_levels import DEFAULT_MEMBER_LEVEL, valid_member_level
from utils.passwords import hash_password
from utils.query import clean_text
from utils.response import ApiError


def _parse_role(value: Any, *, required: bool = True) -> str | None:
    role = clean_text(value)
    if not role:
        if required:
            raise ApiError(400, "角色不能为空", 400)
        return None
    if role not in {"user", "admin"}:
        raise ApiError(400, "角色只能是 user 或 admin", 400)
    return role


def _parse_status(value: Any, *, required: bool = True) -> int | None:
    if value is None or value == "":
        if required:
            raise ApiError(400, "状态不能为空", 400)
        return None
    try:
        status = int(value)
    except (TypeError, ValueError) as exc:
        raise ApiError(400, "状态格式错误", 400) from exc
    if status not in (0, 1):
        raise ApiError(400, "状态只能是0或1", 400)
    return status


def _validate_username(username: str) -> None:
    if not username:
        raise ApiError(400, "用户名不能为空", 400)
    if len(username) > 50:
        raise ApiError(400, "用户名不能超过50个字符", 400)


def _validate_password(password: str) -> None:
    if len(password) < 6:
        raise ApiError(400, "密码长度不能少于6位", 400)


def _parse_member_level(value: Any) -> str:
    try:
        return valid_member_level(value or DEFAULT_MEMBER_LEVEL)
    except ValueError as exc:
        raise ApiError(400, "会员等级只能是 normal、silver、gold 或 diamond", 400) from exc


def _parse_optional_date(value: Any, field_name: str) -> date | None:
    text = clean_text(value)
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ApiError(400, f"{field_name}格式应为 YYYY-MM-DD", 400) from exc


def _parse_change(value: Any, field_name: str) -> int:
    if value is None or value == "":
        return 0
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ApiError(400, f"{field_name}格式错误", 400) from exc


async def list_users(
    settings: Settings,
    *,
    role_arg: Any,
    status_arg: Any,
    page: int,
    page_size: int,
    offset: int,
) -> dict[str, Any]:
    role = _parse_role(role_arg, required=False)
    status = _parse_status(status_arg, required=False)
    rows = await user_repository.list_users(settings, role=role, status=status, offset=offset, limit=page_size)
    total = await user_repository.count_users(settings, role=role, status=status)
    return {"items": [public_user(row) for row in rows], "total": total, "page": page, "page_size": page_size}


async def create_user(settings: Settings, body: dict[str, Any]) -> dict[str, Any]:
    username = clean_text(body.get("username"))
    password = str(body.get("password") or "")
    nickname = clean_text(body.get("nickname")) or username
    contact = clean_text(body.get("contact"))
    role = _parse_role(body.get("role") or "user")
    status = _parse_status(body.get("status") if "status" in body else 1)

    _validate_username(username)
    _validate_password(password)
    if len(nickname) > 50:
        raise ApiError(400, "昵称不能超过50个字符", 400)
    if len(contact) > 50:
        raise ApiError(400, "联系方式不能超过50个字符", 400)
    if await user_repository.get_user_by_username(settings, username):
        raise ApiError(409, "用户名已存在", 409)

    user_id = await user_repository.create_user(
        settings,
        username=username,
        password_hash=await asyncio.to_thread(hash_password, password),
        nickname=nickname,
        role=role or "user",
        contact=contact,
        status=status if status is not None else 1,
    )
    await member_repository.create_default_member_account(settings, user_id)
    user = await user_repository.get_user_by_id(settings, user_id)
    if user is None:
        raise ApiError(500, "创建用户后读取失败", 500)
    return public_user(user)


async def update_user_status(
    settings: Settings,
    *,
    current_user: dict[str, Any],
    user_id: int,
    body: dict[str, Any],
) -> dict[str, Any]:
    if user_id == current_user["id"]:
        raise ApiError(400, "不能修改当前登录账号状态", 400)
    status = _parse_status(body.get("status"))
    user = await user_repository.get_user_by_id(settings, user_id)
    if user is None:
        raise ApiError(404, "用户不存在", 404)
    if status == 0:
        future_count = await reservation_repository.count_future_active_reservations_by_user(settings, user_id=user_id)
        if future_count > 0:
            raise ApiError(409, f"该用户还有 {future_count} 条未来预约，请先取消预约后再禁用", 409)
    await user_repository.update_user_status(settings, user_id, status if status is not None else 1)
    updated = await user_repository.get_user_by_id(settings, user_id)
    if updated is None:
        raise ApiError(404, "用户不存在", 404)
    return public_user(updated)


async def update_user_member(
    settings: Settings,
    *,
    current_user: dict[str, Any],
    user_id: int,
    body: dict[str, Any],
) -> dict[str, Any]:
    user = await user_repository.get_user_by_id(settings, user_id)
    if user is None:
        raise ApiError(404, "用户不存在", 404)

    member_level = _parse_member_level(body.get("member_level", user.get("member_level") or DEFAULT_MEMBER_LEVEL))
    expires_at = (
        _parse_optional_date(body.get("expires_at"), "会员有效期")
        if "expires_at" in body
        else user.get("member_expires_at")
    )
    balance_change_cents = _parse_change(body.get("balance_change_cents"), "余额调整")
    points_change = _parse_change(body.get("points_change"), "积分调整")
    reason = clean_text(body.get("reason")) or "后台调整会员账户"
    if len(reason) > 255:
        raise ApiError(400, "调整原因不能超过255个字符", 400)

    _account, failure = await member_repository.adjust_member_account_atomic(
        settings,
        user_id=user_id,
        member_level=member_level,
        expires_at=expires_at,
        balance_change_cents=balance_change_cents,
        points_change=points_change,
        reason=reason,
        operator_id=current_user.get("id"),
        operator_username=current_user.get("username"),
    )
    if failure == "user_not_found":
        raise ApiError(404, "用户不存在", 404)
    if failure == "insufficient_balance":
        raise ApiError(400, "余额调整后不能小于0", 400)
    if failure == "insufficient_points":
        raise ApiError(400, "积分调整后不能小于0", 400)

    updated = await user_repository.get_user_by_id(settings, user_id)
    if updated is None:
        raise ApiError(404, "用户不存在", 404)
    return public_user(updated)


async def update_user_role(
    settings: Settings,
    *,
    current_user: dict[str, Any],
    user_id: int,
    body: dict[str, Any],
) -> dict[str, Any]:
    if user_id == current_user["id"]:
        raise ApiError(400, "不能修改当前登录账号角色", 400)
    role = _parse_role(body.get("role"))
    user = await user_repository.get_user_by_id(settings, user_id)
    if user is None:
        raise ApiError(404, "用户不存在", 404)
    await user_repository.update_user_role(settings, user_id, role or "user")
    updated = await user_repository.get_user_by_id(settings, user_id)
    if updated is None:
        raise ApiError(404, "用户不存在", 404)
    return public_user(updated)


async def reset_user_password(
    settings: Settings,
    *,
    current_user: dict[str, Any],
    user_id: int,
    body: dict[str, Any],
) -> dict[str, Any]:
    if user_id == current_user["id"]:
        raise ApiError(400, "不能在用户管理中重置当前登录账号密码", 400)
    password = str(body.get("password") or "")
    _validate_password(password)
    user = await user_repository.get_user_by_id(settings, user_id)
    if user is None:
        raise ApiError(404, "用户不存在", 404)
    await user_repository.update_password(settings, user_id, await asyncio.to_thread(hash_password, password))
    await revoke_user_refresh_tokens(settings, user_id)
    updated = await user_repository.get_user_by_id(settings, user_id)
    if updated is None:
        raise ApiError(404, "用户不存在", 404)
    return public_user(updated)
