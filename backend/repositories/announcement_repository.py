from typing import Any

from config.settings import Settings
from repositories.database import execute, fetch_all, fetch_one


ANNOUNCEMENT_COLUMNS = "id, title, content, status, created_by, created_at, updated_at"


async def list_announcements(
    settings: Settings,
    *,
    status: int | None,
    offset: int,
    limit: int,
) -> list[dict[str, Any]]:
    where = []
    args: list[Any] = []
    if status is not None:
        where.append("status = %s")
        args.append(status)
    where_sql = "WHERE " + " AND ".join(where) if where else ""
    args.extend([offset, limit])
    return await fetch_all(
        settings,
        f"""
        SELECT {ANNOUNCEMENT_COLUMNS}
        FROM announcement
        {where_sql}
        ORDER BY created_at DESC, id DESC
        LIMIT %s, %s
        """,
        args,
    )


async def count_announcements(settings: Settings, *, status: int | None) -> int:
    where = []
    args: list[Any] = []
    if status is not None:
        where.append("status = %s")
        args.append(status)
    where_sql = "WHERE " + " AND ".join(where) if where else ""
    row = await fetch_one(settings, f"SELECT COUNT(*) AS total FROM announcement {where_sql}", args)
    return int(row["total"]) if row else 0


async def get_announcement(settings: Settings, announcement_id: int) -> dict[str, Any] | None:
    return await fetch_one(
        settings,
        f"SELECT {ANNOUNCEMENT_COLUMNS} FROM announcement WHERE id = %s",
        (announcement_id,),
    )


async def create_announcement(
    settings: Settings,
    *,
    title: str,
    content: str,
    status: int,
    created_by: int,
) -> int:
    return await execute(
        settings,
        """
        INSERT INTO announcement (title, content, status, created_by)
        VALUES (%s, %s, %s, %s)
        """,
        (title, content, status, created_by),
    )


async def update_announcement(
    settings: Settings,
    *,
    announcement_id: int,
    title: str,
    content: str,
    status: int,
) -> None:
    await execute(
        settings,
        """
        UPDATE announcement
        SET title = %s, content = %s, status = %s
        WHERE id = %s
        """,
        (title, content, status, announcement_id),
    )


async def update_announcement_status(settings: Settings, announcement_id: int, status: int) -> None:
    await execute(settings, "UPDATE announcement SET status = %s WHERE id = %s", (status, announcement_id))
