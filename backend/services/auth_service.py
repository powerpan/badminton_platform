import asyncio
import secrets
import uuid
from typing import Any

from config.settings import Settings
from repositories import member_repository, user_repository
from services import captcha_service, redis_service
from utils.passwords import hash_password, verify_password
from utils.member_levels import public_member
from utils.response import ApiError
from utils.tokens import create_access_token, create_refresh_token, decode_refresh_token


DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD_HASH = "$2b$12$OeO2WdhDYO81lfFsEPMNle//zNjiWq5LuTAFbkK8RPLmv4wVTEAdu"


def _login_fail_key(username: str) -> str:
    return f"auth:fail:{username}"


def _login_lock_key(username: str) -> str:
    return f"auth:lock:{username}"


def _refresh_key(user_id: int, token_id: str) -> str:
    return f"auth:refresh:{user_id}:{token_id}"


def _refresh_pattern(user_id: int) -> str:
    return f"auth:refresh:{user_id}:*"


def _password_reset_key(reset_token: str) -> str:
    return f"auth:password_reset:{reset_token}"


def public_user(user: dict[str, Any]) -> dict[str, Any]:
    member_account = {
        "member_level": user.get("member_level"),
        "balance_cents": user.get("balance_cents"),
        "points": user.get("points"),
        "expires_at": user.get("member_expires_at"),
    }
    return {
        "id": user["id"],
        "username": user["username"],
        "nickname": user.get("nickname") or "",
        "role": user["role"],
        "contact": user.get("contact") or "",
        "status": user["status"],
        "member": public_member(member_account),
    }


async def public_current_user(user: dict[str, Any]) -> dict[str, Any]:
    data = public_user(user)
    data["must_change_password"] = await is_default_admin_password(user)
    return data


async def is_default_admin_password(user: dict[str, Any]) -> bool:
    if user.get("username") != DEFAULT_ADMIN_USERNAME or user.get("role") != "admin":
        return False
    return user.get("password_hash") == DEFAULT_ADMIN_PASSWORD_HASH


async def _hash_password(password: str) -> str:
    return await asyncio.to_thread(hash_password, password)


async def _verify_password(password: str, password_hash: str) -> bool:
    return await asyncio.to_thread(verify_password, password, password_hash)


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

    await captcha_service.verify_captcha(settings, body.get("captcha_id"), body.get("captcha_code"))
    _validate_username(username)
    _validate_password(password)

    existing_user = await user_repository.get_user_by_username(settings, username)
    if existing_user:
        raise ApiError(409, "用户名已存在", 409)

    user_id = await user_repository.create_user(
        settings,
        username=username,
        password_hash=await _hash_password(password),
        nickname=nickname,
        contact=contact,
    )
    await member_repository.create_default_member_account(settings, user_id)
    user = await user_repository.get_user_by_id(settings, user_id)
    if user is None:
        raise ApiError(500, "注册成功但读取用户信息失败", 500)
    return public_user(user)


async def login(settings: Settings, body: dict[str, Any]) -> dict[str, Any]:
    username = _clean_text(body.get("username"))
    password = str(body.get("password") or "")

    await captcha_service.verify_captcha(settings, body.get("captcha_id"), body.get("captcha_code"))
    _validate_username(username)
    if not password:
        raise ApiError(400, "密码不能为空", 400)

    lock_key = _login_lock_key(username)
    if await redis_service.get_value(settings, lock_key):
        seconds = await redis_service.ttl(settings, lock_key)
        raise ApiError(423, f"登录失败次数过多，请 {max(seconds, 1)} 秒后再试", 423)

    user = await user_repository.get_user_by_username(settings, username)
    if user is None or not await _verify_password(password, user["password_hash"]):
        fail_count = await redis_service.increment_with_ttl(
            settings,
            _login_fail_key(username),
            settings.login_fail_window_seconds,
        )
        if fail_count >= settings.login_fail_max:
            await redis_service.set_value(settings, lock_key, "1", settings.login_lock_seconds)
            await redis_service.delete_keys(settings, _login_fail_key(username))
            raise ApiError(423, "登录失败次数过多，账号已短暂锁定", 423)
        raise ApiError(400, "用户名或密码错误", 400)
    if user["status"] != 1:
        raise ApiError(403, "账号已被禁用", 403)

    await redis_service.delete_keys(settings, _login_fail_key(username), lock_key)
    await user_repository.update_last_login(settings, user["id"])
    token, refresh_token = await issue_tokens(settings, user)
    return {
        "token": token,
        "access_token": token,
        "refresh_token": refresh_token,
        "user": await public_current_user(user),
    }


async def issue_tokens(settings: Settings, user: dict[str, Any]) -> tuple[str, str]:
    token = create_access_token(
        user_id=user["id"],
        username=user["username"],
        role=user["role"],
        secret=settings.jwt_secret,
        expire_seconds=settings.jwt_expire_seconds,
    )
    token_id = uuid.uuid4().hex
    refresh_token = create_refresh_token(
        user_id=user["id"],
        username=user["username"],
        role=user["role"],
        token_id=token_id,
        secret=settings.jwt_secret,
        expire_seconds=settings.jwt_refresh_expire_seconds,
    )
    await redis_service.set_value(
        settings,
        _refresh_key(user["id"], token_id),
        "1",
        settings.jwt_refresh_expire_seconds,
    )
    return token, refresh_token


async def refresh_login(settings: Settings, body: dict[str, Any]) -> dict[str, Any]:
    refresh_token = _clean_text(body.get("refresh_token"))
    if not refresh_token:
        raise ApiError(401, "请重新登录", 401)
    payload = decode_refresh_token(refresh_token, settings.jwt_secret)
    user_id = payload["user_id"]
    token_id = payload["token_id"]
    key = _refresh_key(user_id, token_id)
    if not await redis_service.get_value(settings, key):
        raise ApiError(401, "登录状态已失效，请重新登录", 401)

    user = await user_repository.get_user_by_id(settings, user_id)
    if user is None:
        raise ApiError(401, "登录用户不存在，请重新登录", 401)
    if user["status"] != 1:
        raise ApiError(403, "账号已被禁用", 403)

    await redis_service.delete_keys(settings, key)
    token, new_refresh_token = await issue_tokens(settings, user)
    return {
        "token": token,
        "access_token": token,
        "refresh_token": new_refresh_token,
        "user": await public_current_user(user),
    }


async def logout(settings: Settings, body: dict[str, Any]) -> None:
    refresh_token = _clean_text(body.get("refresh_token"))
    if not refresh_token:
        return
    try:
        payload = decode_refresh_token(refresh_token, settings.jwt_secret)
    except ApiError:
        return
    await redis_service.delete_keys(settings, _refresh_key(payload["user_id"], payload["token_id"]))


async def revoke_user_refresh_tokens(settings: Settings, user_id: int) -> None:
    await redis_service.delete_pattern(settings, _refresh_pattern(user_id))


async def request_password_reset(settings: Settings, body: dict[str, Any]) -> dict[str, Any]:
    username = _clean_text(body.get("username"))
    contact = _clean_text(body.get("contact"))

    await captcha_service.verify_captcha(settings, body.get("captcha_id"), body.get("captcha_code"))
    _validate_username(username)
    if not contact:
        raise ApiError(400, "联系方式不能为空", 400)

    user = await user_repository.get_user_by_username(settings, username)
    if user is None or _clean_text(user.get("contact")) != contact:
        raise ApiError(400, "用户名或联系方式不匹配", 400)
    if user["status"] != 1:
        raise ApiError(403, "账号已被禁用", 403)

    reset_token = secrets.token_urlsafe(32)
    await redis_service.set_value(
        settings,
        _password_reset_key(reset_token),
        str(user["id"]),
        settings.password_reset_expire_seconds,
    )
    return {
        "reset_token": reset_token,
        "expires_in": settings.password_reset_expire_seconds,
    }


async def confirm_password_reset(settings: Settings, body: dict[str, Any]) -> None:
    reset_token = _clean_text(body.get("reset_token"))
    new_password = str(body.get("new_password") or "")
    if not reset_token:
        raise ApiError(400, "重置凭证不能为空", 400)
    _validate_password(new_password)

    key = _password_reset_key(reset_token)
    user_id_text = await redis_service.get_value(settings, key)
    if user_id_text is None:
        raise ApiError(401, "重置凭证已失效，请重新验证", 401)

    try:
        user_id = int(user_id_text)
    except ValueError as exc:
        await redis_service.delete_keys(settings, key)
        raise ApiError(401, "重置凭证已失效，请重新验证", 401) from exc

    user = await user_repository.get_user_by_id(settings, user_id)
    if user is None:
        await redis_service.delete_keys(settings, key)
        raise ApiError(404, "用户不存在", 404)
    if user["status"] != 1:
        raise ApiError(403, "账号已被禁用", 403)

    await user_repository.update_password(settings, user_id, await _hash_password(new_password))
    await redis_service.delete_keys(settings, key, _login_fail_key(user["username"]), _login_lock_key(user["username"]))
    await revoke_user_refresh_tokens(settings, user_id)


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
    return await public_current_user(user)


async def change_password(
    settings: Settings,
    current_user: dict[str, Any],
    body: dict[str, Any],
) -> None:
    old_password = str(body.get("old_password") or "")
    new_password = str(body.get("new_password") or "")

    if not await _verify_password(old_password, current_user["password_hash"]):
        raise ApiError(400, "旧密码错误", 400)
    _validate_password(new_password)

    await user_repository.update_password(settings, current_user["id"], await _hash_password(new_password))
    await revoke_user_refresh_tokens(settings, current_user["id"])
