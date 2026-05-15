from datetime import datetime
from typing import Any

import aiomysql

from config.settings import Settings
from repositories.database import execute, fetch_all, fetch_one, get_pool


NOTIFICATION_COLUMNS = """
    id, user_id, title, content, category, source_type, source_id,
    is_read, read_at, created_by, created_at
"""


async def list_notifications(
    settings: Settings,
    *,
    user_id: int,
    is_read: int | None,
    offset: int,
    limit: int,
) -> list[dict[str, Any]]:
    where = ["user_id = %s"]
    args: list[Any] = [user_id]
    if is_read is not None:
        where.append("is_read = %s")
        args.append(is_read)
    args.extend([offset, limit])
    return await fetch_all(
        settings,
        f"""
        SELECT {NOTIFICATION_COLUMNS}
        FROM notification
        WHERE {" AND ".join(where)}
        ORDER BY is_read ASC, created_at DESC, id DESC
        LIMIT %s, %s
        """,
        args,
    )


async def count_notifications(settings: Settings, *, user_id: int, is_read: int | None) -> int:
    where = ["user_id = %s"]
    args: list[Any] = [user_id]
    if is_read is not None:
        where.append("is_read = %s")
        args.append(is_read)
    row = await fetch_one(
        settings,
        f"SELECT COUNT(*) AS total FROM notification WHERE {' AND '.join(where)}",
        args,
    )
    return int(row["total"]) if row else 0


async def count_unread_notifications(settings: Settings, *, user_id: int) -> int:
    row = await fetch_one(
        settings,
        "SELECT COUNT(*) AS total FROM notification WHERE user_id = %s AND is_read = 0",
        (user_id,),
    )
    return int(row["total"]) if row else 0


async def get_notification(settings: Settings, *, user_id: int, notification_id: int) -> dict[str, Any] | None:
    return await fetch_one(
        settings,
        f"""
        SELECT {NOTIFICATION_COLUMNS}
        FROM notification
        WHERE id = %s AND user_id = %s
        """,
        (notification_id, user_id),
    )


async def create_notification(
    settings: Settings,
    *,
    user_id: int,
    title: str,
    content: str,
    category: str,
    source_type: str | None,
    source_id: int | None,
    created_by: int | None,
) -> int:
    return await execute(
        settings,
        """
        INSERT INTO notification
          (user_id, title, content, category, source_type, source_id, created_by)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (user_id, title, content, category, source_type, source_id, created_by),
    )


async def list_enabled_user_ids(settings: Settings) -> list[int]:
    rows = await fetch_all(settings, "SELECT id FROM user WHERE status = 1 ORDER BY id ASC")
    return [int(row["id"]) for row in rows]


async def create_notifications_for_users(
    settings: Settings,
    *,
    user_ids: list[int],
    title: str,
    content: str,
    category: str,
    source_type: str | None,
    source_id: int | None,
    created_by: int | None,
    created_at: datetime,
) -> int:
    if not user_ids:
        return 0
    rows = [
        (user_id, title, content, category, source_type, source_id, created_by, created_at)
        for user_id in user_ids
    ]
    pool = await get_pool(settings)
    async with pool.acquire() as connection:
        async with connection.cursor(aiomysql.DictCursor) as cursor:
            await cursor.executemany(
                """
                INSERT INTO notification
                  (user_id, title, content, category, source_type, source_id, created_by, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                rows,
            )
            return int(cursor.rowcount)


async def mark_notification_read(settings: Settings, *, user_id: int, notification_id: int) -> None:
    await execute(
        settings,
        """
        UPDATE notification
        SET is_read = 1, read_at = COALESCE(read_at, NOW())
        WHERE id = %s AND user_id = %s
        """,
        (notification_id, user_id),
    )


async def mark_all_read(settings: Settings, *, user_id: int) -> int:
    return await execute(
        settings,
        """
        UPDATE notification
        SET is_read = 1, read_at = COALESCE(read_at, NOW())
        WHERE user_id = %s AND is_read = 0
        """,
        (user_id,),
    )
