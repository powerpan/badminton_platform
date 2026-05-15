from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from utils.response import ApiError


def create_access_token(
    *,
    user_id: int,
    username: str,
    role: str,
    secret: str,
    expire_seconds: int,
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "user_id": user_id,
        "username": username,
        "role": role,
        "iat": now,
        "exp": now + timedelta(seconds=expire_seconds),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_access_token(token: str, secret: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as exc:
        raise ApiError(401, "登录已过期，请重新登录", 401) from exc
    except jwt.InvalidTokenError as exc:
        raise ApiError(401, "登录状态无效，请重新登录", 401) from exc

    user_id = payload.get("user_id")
    if not isinstance(user_id, int):
        raise ApiError(401, "登录状态无效，请重新登录", 401)
    return payload
