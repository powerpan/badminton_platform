from typing import Any

from config.settings import Settings
from repositories import user_repository
from utils.passwords import hash_password, verify_password
from utils.response import ApiError
from utils.tokens import create_access_token


def public_user(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": user["id"],
        "username": user["username"],
        "nickname": user.get("nickname") or "",
        "role": user["role"],
        "contact": user.get("contact") or "",
        "status": user["status"],
    }


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _validate_username(username: str) -> None:
    if not username:
        raise ApiError(400, "用户名不能为空", 400)
    if len(username) > 50:
        raise ApiError(400, "用户名不能超过50个字符", 400)


def _validate_password(password: str) -> None:
    if len(password) < 6:
        raise ApiError(400, "密码长度不能少于6位", 400)


async def register(settings: Settings, body: dict[str, Any]) -> dict[str, Any]:
    username = _clean_text(body.get("username"))
    password = str(body.get("password") or "")
    nickname = _clean_text(body.get("nickname")) or username
    contact = _clean_text(body.get("contact"))

    _validate_username(username)
    _validate_password(password)

    existing_user = await user_repository.get_user_by_username(settings, username)
    if existing_user:
        raise ApiError(409, "用户名已存在", 409)

    user_id = await user_repository.create_user(
        settings,
        username=username,
        password_hash=hash_password(password),
        nickname=nickname,
        contact=contact,
    )
    user = await user_repository.get_user_by_id(settings, user_id)
    if user is None:
        raise ApiError(500, "注册成功但读取用户信息失败", 500)
    return public_user(user)


async def login(settings: Settings, body: dict[str, Any]) -> dict[str, Any]:
    username = _clean_text(body.get("username"))
    password = str(body.get("password") or "")

    _validate_username(username)
    if not password:
        raise ApiError(400, "密码不能为空", 400)

    user = await user_repository.get_user_by_username(settings, username)
    if user is None or not verify_password(password, user["password_hash"]):
        raise ApiError(400, "用户名或密码错误", 400)
    if user["status"] != 1:
        raise ApiError(403, "账号已被禁用", 403)

    await user_repository.update_last_login(settings, user["id"])
    token = create_access_token(
        user_id=user["id"],
        username=user["username"],
        role=user["role"],
        secret=settings.jwt_secret,
        expire_seconds=settings.jwt_expire_seconds,
    )
    return {
        "token": token,
        "user": public_user(user),
    }


async def update_profile(
    settings: Settings,
    current_user: dict[str, Any],
    body: dict[str, Any],
) -> dict[str, Any]:
    nickname = _clean_text(body.get("nickname")) or current_user["username"]
    contact = _clean_text(body.get("contact"))

    if len(nickname) > 50:
        raise ApiError(400, "昵称不能超过50个字符", 400)
    if len(contact) > 50:
        raise ApiError(400, "联系方式不能超过50个字符", 400)

    await user_repository.update_profile(settings, current_user["id"], nickname, contact)
    user = await user_repository.get_user_by_id(settings, current_user["id"])
    if user is None:
        raise ApiError(404, "用户不存在", 404)
    return public_user(user)


async def change_password(
    settings: Settings,
    current_user: dict[str, Any],
    body: dict[str, Any],
) -> None:
    old_password = str(body.get("old_password") or "")
    new_password = str(body.get("new_password") or "")

    if not verify_password(old_password, current_user["password_hash"]):
        raise ApiError(400, "旧密码错误", 400)
    _validate_password(new_password)

    await user_repository.update_password(settings, current_user["id"], hash_password(new_password))
