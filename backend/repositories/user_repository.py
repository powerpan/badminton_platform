from typing import Any

from config.settings import Settings
from repositories.database import execute, fetch_one


USER_COLUMNS = """
    id, username, password_hash, nickname, role, contact, status,
    last_login_at, created_at, updated_at
"""


async def get_user_by_id(settings: Settings, user_id: int) -> dict[str, Any] | None:
    return await fetch_one(
        settings,
        f"SELECT {USER_COLUMNS} FROM user WHERE id = %s",
        (user_id,),
    )


async def get_user_by_username(settings: Settings, username: str) -> dict[str, Any] | None:
    return await fetch_one(
        settings,
        f"SELECT {USER_COLUMNS} FROM user WHERE username = %s",
        (username,),
    )


async def create_user(
    settings: Settings,
    *,
    username: str,
    password_hash: str,
    nickname: str,
    contact: str,
    role: str = "user",
    status: int = 1,
) -> int:
    return await execute(
        settings,
        """
        INSERT INTO user (username, password_hash, nickname, role, contact, status)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (username, password_hash, nickname, role, contact, status),
    )


async def update_last_login(settings: Settings, user_id: int) -> None:
    await execute(
        settings,
        "UPDATE user SET last_login_at = NOW() WHERE id = %s",
        (user_id,),
    )


async def update_profile(settings: Settings, user_id: int, nickname: str, contact: str) -> None:
    await execute(
        settings,
        "UPDATE user SET nickname = %s, contact = %s WHERE id = %s",
        (nickname, contact, user_id),
    )


async def update_password(settings: Settings, user_id: int, password_hash: str) -> None:
    await execute(
        settings,
        "UPDATE user SET password_hash = %s WHERE id = %s",
        (password_hash, user_id),
    )
