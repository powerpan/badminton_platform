from typing import Any

from config.settings import Settings
from repositories.database import execute, fetch_all, fetch_one


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


async def list_users(
    settings: Settings,
    *,
    role: str | None,
    status: int | None,
    offset: int,
    limit: int,
) -> list[dict[str, Any]]:
    where = []
    args: list[Any] = []
    if role:
        where.append("role = %s")
        args.append(role)
    if status is not None:
        where.append("status = %s")
        args.append(status)
    where_sql = "WHERE " + " AND ".join(where) if where else ""
    args.extend([offset, limit])
    return await fetch_all(
        settings,
        f"""
        SELECT {USER_COLUMNS}
        FROM user
        {where_sql}
        ORDER BY id DESC
        LIMIT %s, %s
        """,
        args,
    )


async def count_users(settings: Settings, *, role: str | None, status: int | None) -> int:
    where = []
    args: list[Any] = []
    if role:
        where.append("role = %s")
        args.append(role)
    if status is not None:
        where.append("status = %s")
        args.append(status)
    where_sql = "WHERE " + " AND ".join(where) if where else ""
    row = await fetch_one(settings, f"SELECT COUNT(*) AS total FROM user {where_sql}", args)
    return int(row["total"]) if row else 0


async def update_user_status(settings: Settings, user_id: int, status: int) -> None:
    await execute(settings, "UPDATE user SET status = %s WHERE id = %s", (status, user_id))


async def update_user_role(settings: Settings, user_id: int, role: str) -> None:
    await execute(settings, "UPDATE user SET role = %s WHERE id = %s", (role, user_id))
