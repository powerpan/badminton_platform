from typing import Any

from config.settings import Settings
from repositories.database import execute, fetch_all, fetch_one


COURT_COLUMNS = (
    "id, court_no, court_name, description, status, price_per_hour_cents, image_url, tags, capacity, "
    "created_at, updated_at"
)


async def list_courts(
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
        SELECT {COURT_COLUMNS}
        FROM court
        {where_sql}
        ORDER BY court_no ASC
        LIMIT %s, %s
        """,
        args,
    )


async def count_courts(settings: Settings, *, status: int | None) -> int:
    where = []
    args: list[Any] = []
    if status is not None:
        where.append("status = %s")
        args.append(status)
    where_sql = "WHERE " + " AND ".join(where) if where else ""
    row = await fetch_one(settings, f"SELECT COUNT(*) AS total FROM court {where_sql}", args)
    return int(row["total"]) if row else 0


async def get_court_by_id(settings: Settings, court_id: int) -> dict[str, Any] | None:
    return await fetch_one(settings, f"SELECT {COURT_COLUMNS} FROM court WHERE id = %s", (court_id,))


async def get_court_by_no(settings: Settings, court_no: str) -> dict[str, Any] | None:
    return await fetch_one(settings, f"SELECT {COURT_COLUMNS} FROM court WHERE court_no = %s", (court_no,))


async def create_court(
    settings: Settings,
    *,
    court_no: str,
    court_name: str,
    description: str,
    status: int,
    price_per_hour_cents: int,
    image_url: str,
    tags: str,
    capacity: int,
) -> int:
    return await execute(
        settings,
        """
        INSERT INTO court (court_no, court_name, description, status, price_per_hour_cents, image_url, tags, capacity)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (court_no, court_name, description, status, price_per_hour_cents, image_url, tags, capacity),
    )


async def update_court(
    settings: Settings,
    *,
    court_id: int,
    court_no: str,
    court_name: str,
    description: str,
    status: int,
    price_per_hour_cents: int,
    image_url: str,
    tags: str,
    capacity: int,
) -> None:
    await execute(
        settings,
        """
        UPDATE court
        SET court_no = %s,
            court_name = %s,
            description = %s,
            status = %s,
            price_per_hour_cents = %s,
            image_url = %s,
            tags = %s,
            capacity = %s
        WHERE id = %s
        """,
        (court_no, court_name, description, status, price_per_hour_cents, image_url, tags, capacity, court_id),
    )


async def update_court_status(settings: Settings, court_id: int, status: int) -> None:
    await execute(settings, "UPDATE court SET status = %s WHERE id = %s", (status, court_id))
