from typing import Any

from config.settings import Settings
from repositories.database import execute, fetch_all, fetch_one


POST_COLUMNS = (
    "p.id, p.user_id, u.username, u.nickname, p.content, p.status, p.created_at, p.updated_at"
)


async def list_posts(
    settings: Settings,
    *,
    status: int | None,
    offset: int,
    limit: int,
) -> list[dict[str, Any]]:
    where = []
    args: list[Any] = []
    if status is not None:
        where.append("p.status = %s")
        args.append(status)
    where_sql = "WHERE " + " AND ".join(where) if where else ""
    args.extend([offset, limit])
    return await fetch_all(
        settings,
        f"""
        SELECT {POST_COLUMNS}
        FROM community_post p
        JOIN user u ON u.id = p.user_id
        {where_sql}
        ORDER BY p.created_at DESC, p.id DESC
        LIMIT %s, %s
        """,
        args,
    )


async def count_posts(settings: Settings, *, status: int | None) -> int:
    where = []
    args: list[Any] = []
    if status is not None:
        where.append("status = %s")
        args.append(status)
    where_sql = "WHERE " + " AND ".join(where) if where else ""
    row = await fetch_one(settings, f"SELECT COUNT(*) AS total FROM community_post {where_sql}", args)
    return int(row["total"]) if row else 0


async def get_post(settings: Settings, post_id: int) -> dict[str, Any] | None:
    return await fetch_one(
        settings,
        f"""
        SELECT {POST_COLUMNS}
        FROM community_post p
        JOIN user u ON u.id = p.user_id
        WHERE p.id = %s
        """,
        (post_id,),
    )


async def create_post(settings: Settings, *, user_id: int, content: str) -> int:
    return await execute(
        settings,
        "INSERT INTO community_post (user_id, content, status) VALUES (%s, %s, 1)",
        (user_id, content),
    )


async def hide_post(settings: Settings, *, post_id: int, user_id: int | None = None) -> int:
    where = ["id = %s", "status = 1"]
    args: list[Any] = [post_id]
    if user_id is not None:
        where.append("user_id = %s")
        args.append(user_id)
    return await execute(
        settings,
        f"UPDATE community_post SET status = 0 WHERE {' AND '.join(where)}",
        args,
    )
