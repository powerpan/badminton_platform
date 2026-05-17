from datetime import date
from typing import Any

from config.settings import Settings
from repositories.database import fetch_all, fetch_one


async def get_user_counts(settings: Settings) -> dict[str, int]:
    row = await fetch_one(
        settings,
        """
        SELECT
          COUNT(*) AS total_users,
          SUM(CASE WHEN status = 1 THEN 1 ELSE 0 END) AS enabled_users,
          SUM(CASE WHEN role = 'admin' THEN 1 ELSE 0 END) AS admin_users
        FROM user
        """,
    )
    return {
        "total_users": int(row["total_users"] or 0) if row else 0,
        "enabled_users": int(row["enabled_users"] or 0) if row else 0,
        "admin_users": int(row["admin_users"] or 0) if row else 0,
    }


async def get_court_counts(settings: Settings) -> dict[str, int]:
    row = await fetch_one(
        settings,
        """
        SELECT
          COUNT(*) AS total_courts,
          SUM(CASE WHEN status = 1 THEN 1 ELSE 0 END) AS enabled_courts
        FROM court
        """,
    )
    return {
        "total_courts": int(row["total_courts"] or 0) if row else 0,
        "enabled_courts": int(row["enabled_courts"] or 0) if row else 0,
    }


async def get_reservation_status_counts(
    settings: Settings,
    *,
    date_from: date,
    date_to: date,
) -> dict[str, int]:
    rows = await fetch_all(
        settings,
        """
        SELECT status, COUNT(*) AS total
        FROM reservation
        WHERE reserve_date BETWEEN %s AND %s
        GROUP BY status
        """,
        (date_from, date_to),
    )
    counts = {str(row["status"]): int(row["total"] or 0) for row in rows}
    counts["total"] = sum(counts.values())
    return counts


async def count_today_reservations(settings: Settings) -> int:
    row = await fetch_one(
        settings,
        """
        SELECT COUNT(*) AS total
        FROM reservation
        WHERE reserve_date = CURDATE()
          AND status IN ('pending', 'confirmed', 'completed')
        """,
    )
    return int(row["total"] or 0) if row else 0


async def count_active_users(settings: Settings, *, date_from: date, date_to: date) -> int:
    row = await fetch_one(
        settings,
        """
        SELECT COUNT(DISTINCT user_id) AS total
        FROM reservation
        WHERE reserve_date BETWEEN %s AND %s
          AND status IN ('pending', 'confirmed', 'completed')
        """,
        (date_from, date_to),
    )
    return int(row["total"] or 0) if row else 0


async def list_court_usage(settings: Settings, *, date_from: date, date_to: date) -> list[dict[str, Any]]:
    return await fetch_all(
        settings,
        """
        SELECT
          c.id,
          c.court_no,
          c.court_name,
          c.status,
          COUNT(r.id) AS reservation_count,
          SUM(CASE WHEN r.status IN ('pending', 'confirmed', 'completed') THEN 1 ELSE 0 END) AS active_count,
          SUM(CASE
            WHEN r.status IN ('pending', 'confirmed', 'completed')
            THEN TIME_TO_SEC(TIMEDIFF(r.end_time, r.start_time)) / 3600
            ELSE 0
          END) AS booked_hours
        FROM court c
        LEFT JOIN reservation r
          ON r.court_id = c.id
         AND r.reserve_date BETWEEN %s AND %s
        GROUP BY c.id, c.court_no, c.court_name, c.status
        ORDER BY active_count DESC, c.court_no ASC
        """,
        (date_from, date_to),
    )


async def list_time_slot_usage(
    settings: Settings,
    *,
    date_from: date,
    date_to: date,
    limit: int,
) -> list[dict[str, Any]]:
    return await fetch_all(
        settings,
        """
        SELECT
          time_slot,
          start_time,
          end_time,
          COUNT(*) AS reservation_count
        FROM reservation
        WHERE reserve_date BETWEEN %s AND %s
          AND status IN ('pending', 'confirmed', 'completed')
        GROUP BY time_slot, start_time, end_time
        ORDER BY reservation_count DESC, start_time ASC
        LIMIT %s
        """,
        (date_from, date_to, limit),
    )


async def list_user_activity(
    settings: Settings,
    *,
    date_from: date,
    date_to: date,
    limit: int,
) -> list[dict[str, Any]]:
    return await fetch_all(
        settings,
        """
        SELECT
          u.id AS user_id,
          u.username,
          u.nickname,
          COUNT(r.id) AS reservation_count,
          SUM(CASE WHEN r.status = 'confirmed' THEN 1 ELSE 0 END) AS confirmed_count,
          SUM(CASE WHEN r.status = 'completed' THEN 1 ELSE 0 END) AS completed_count,
          SUM(CASE WHEN r.status = 'canceled' THEN 1 ELSE 0 END) AS canceled_count,
          MAX(r.reserve_date) AS last_reserve_date
        FROM user u
        JOIN reservation r ON r.user_id = u.id
        WHERE r.reserve_date BETWEEN %s AND %s
        GROUP BY u.id, u.username, u.nickname
        ORDER BY reservation_count DESC, last_reserve_date DESC
        LIMIT %s
        """,
        (date_from, date_to, limit),
    )
