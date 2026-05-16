from datetime import datetime
from typing import Any

import aiomysql

from config.settings import Settings
from repositories.database import execute, fetch_all, fetch_one, get_pool


EVENT_COLUMNS = (
    "e.id, e.title, e.content, e.location, e.start_at, e.end_at, e.registration_deadline, "
    "e.capacity, e.status, e.created_by, e.created_at, e.updated_at"
)


def _event_select(user_id: int | None = None) -> str:
    my_registration_sql = (
        "MAX(CASE WHEN er_me.user_id IS NULL THEN 0 ELSE 1 END) AS is_registered"
        if user_id
        else "0 AS is_registered"
    )
    return f"""
        SELECT {EVENT_COLUMNS},
               COUNT(er_active.id) AS registered_count,
               {my_registration_sql}
        FROM club_event e
        LEFT JOIN event_registration er_active
          ON er_active.event_id = e.id AND er_active.status = 'active'
        {("LEFT JOIN event_registration er_me ON er_me.event_id = e.id AND er_me.user_id = %s AND er_me.status = 'active'") if user_id else ""}
    """


async def list_events(
    settings: Settings,
    *,
    status: int | None,
    user_id: int | None,
    offset: int,
    limit: int,
) -> list[dict[str, Any]]:
    where = []
    args: list[Any] = []
    if user_id:
        args.append(user_id)
    if status is not None:
        where.append("e.status = %s")
        args.append(status)
    where_sql = "WHERE " + " AND ".join(where) if where else ""
    args.extend([offset, limit])
    return await fetch_all(
        settings,
        f"""
        {_event_select(user_id)}
        {where_sql}
        GROUP BY e.id
        ORDER BY e.start_at ASC, e.id DESC
        LIMIT %s, %s
        """,
        args,
    )


async def count_events(settings: Settings, *, status: int | None) -> int:
    where = []
    args: list[Any] = []
    if status is not None:
        where.append("status = %s")
        args.append(status)
    where_sql = "WHERE " + " AND ".join(where) if where else ""
    row = await fetch_one(settings, f"SELECT COUNT(*) AS total FROM club_event {where_sql}", args)
    return int(row["total"]) if row else 0


async def get_event(settings: Settings, event_id: int, *, user_id: int | None = None) -> dict[str, Any] | None:
    args: list[Any] = []
    if user_id:
        args.append(user_id)
    args.append(event_id)
    return await fetch_one(
        settings,
        f"""
        {_event_select(user_id)}
        WHERE e.id = %s
        GROUP BY e.id
        """,
        args,
    )


async def create_event(
    settings: Settings,
    *,
    title: str,
    content: str,
    location: str,
    start_at: datetime,
    end_at: datetime,
    registration_deadline: datetime,
    capacity: int,
    status: int,
    created_by: int | None,
) -> int:
    return await execute(
        settings,
        """
        INSERT INTO club_event
          (title, content, location, start_at, end_at, registration_deadline, capacity, status, created_by)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (title, content, location, start_at, end_at, registration_deadline, capacity, status, created_by),
    )


async def update_event(
    settings: Settings,
    *,
    event_id: int,
    title: str,
    content: str,
    location: str,
    start_at: datetime,
    end_at: datetime,
    registration_deadline: datetime,
    capacity: int,
    status: int,
) -> None:
    await execute(
        settings,
        """
        UPDATE club_event
        SET title = %s,
            content = %s,
            location = %s,
            start_at = %s,
            end_at = %s,
            registration_deadline = %s,
            capacity = %s,
            status = %s
        WHERE id = %s
        """,
        (title, content, location, start_at, end_at, registration_deadline, capacity, status, event_id),
    )


async def update_event_status(settings: Settings, event_id: int, status: int) -> None:
    await execute(settings, "UPDATE club_event SET status = %s WHERE id = %s", (status, event_id))


async def register_event_atomic(settings: Settings, *, event_id: int, user_id: int) -> tuple[bool, str | None]:
    pool = await get_pool(settings)
    async with pool.acquire() as connection:
        await connection.autocommit(False)
        try:
            await connection.begin()
            async with connection.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute("SELECT id, status FROM user WHERE id = %s FOR UPDATE", (user_id,))
                user = await cursor.fetchone()
                if user is None:
                    await connection.rollback()
                    return False, "user_not_found"
                if user["status"] != 1:
                    await connection.rollback()
                    return False, "user_disabled"

                await cursor.execute(
                    """
                    SELECT id, status, registration_deadline, capacity
                    FROM club_event
                    WHERE id = %s
                    FOR UPDATE
                    """,
                    (event_id,),
                )
                event = await cursor.fetchone()
                if event is None:
                    await connection.rollback()
                    return False, "not_found"
                if event["status"] != 1:
                    await connection.rollback()
                    return False, "hidden"
                if event["registration_deadline"] < datetime.now():
                    await connection.rollback()
                    return False, "deadline_passed"

                await cursor.execute(
                    """
                    SELECT id
                    FROM event_registration
                    WHERE event_id = %s AND status = 'active'
                    FOR UPDATE
                    """,
                    (event_id,),
                )
                active_rows = await cursor.fetchall()
                if len(active_rows) >= int(event["capacity"]):
                    await connection.rollback()
                    return False, "full"

                await cursor.execute(
                    """
                    SELECT id, status
                    FROM event_registration
                    WHERE event_id = %s AND user_id = %s
                    FOR UPDATE
                    """,
                    (event_id, user_id),
                )
                registration = await cursor.fetchone()
                if registration and registration["status"] == "active":
                    await connection.rollback()
                    return False, "already_registered"
                if registration:
                    await cursor.execute(
                        """
                        UPDATE event_registration
                        SET status = 'active', registered_at = NOW(), canceled_at = NULL
                        WHERE id = %s
                        """,
                        (registration["id"],),
                    )
                else:
                    await cursor.execute(
                        """
                        INSERT INTO event_registration (event_id, user_id, status)
                        VALUES (%s, %s, 'active')
                        """,
                        (event_id, user_id),
                    )
            await connection.commit()
            return True, None
        except Exception:
            await connection.rollback()
            raise
        finally:
            await connection.autocommit(True)


async def cancel_registration_atomic(settings: Settings, *, event_id: int, user_id: int) -> tuple[bool, str | None]:
    pool = await get_pool(settings)
    async with pool.acquire() as connection:
        await connection.autocommit(False)
        try:
            await connection.begin()
            async with connection.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute("SELECT id FROM club_event WHERE id = %s FOR UPDATE", (event_id,))
                if await cursor.fetchone() is None:
                    await connection.rollback()
                    return False, "not_found"
                await cursor.execute(
                    """
                    SELECT id, status
                    FROM event_registration
                    WHERE event_id = %s AND user_id = %s
                    FOR UPDATE
                    """,
                    (event_id, user_id),
                )
                registration = await cursor.fetchone()
                if registration is None or registration["status"] != "active":
                    await connection.rollback()
                    return False, "not_registered"
                await cursor.execute(
                    """
                    UPDATE event_registration
                    SET status = 'canceled', canceled_at = NOW()
                    WHERE id = %s
                    """,
                    (registration["id"],),
                )
            await connection.commit()
            return True, None
        except Exception:
            await connection.rollback()
            raise
        finally:
            await connection.autocommit(True)


async def list_active_registration_user_ids(settings: Settings, event_id: int) -> list[int]:
    rows = await fetch_all(
        settings,
        """
        SELECT user_id
        FROM event_registration
        WHERE event_id = %s AND status = 'active'
        """,
        (event_id,),
    )
    return [int(row["user_id"]) for row in rows]
