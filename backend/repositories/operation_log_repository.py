from datetime import datetime
from typing import Any

from config.settings import Settings
from repositories.database import execute, fetch_all, fetch_one


async def create_operation_log(
    settings: Settings,
    *,
    user_id: int | None,
    username: str | None,
    role: str | None,
    module: str,
    action: str,
    target_type: str | None,
    target_id: int | None,
    detail: str,
    ip: str | None,
) -> int:
    return await execute(
        settings,
        """
        INSERT INTO operation_log
          (user_id, username, role, module, action, target_type, target_id, detail, ip)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (user_id, username, role, module, action, target_type, target_id, detail, ip),
    )


async def list_operation_logs(
    settings: Settings,
    *,
    module: str | None,
    action: str | None,
    username: str | None,
    start_at: datetime | None,
    end_at: datetime | None,
    offset: int,
    limit: int,
) -> list[dict[str, Any]]:
    where, args = _build_where(module=module, action=action, username=username, start_at=start_at, end_at=end_at)
    args.extend([offset, limit])
    return await fetch_all(
        settings,
        f"""
        SELECT id, user_id, username, role, module, action, target_type, target_id, detail, ip, created_at
        FROM operation_log
        {where}
        ORDER BY created_at DESC, id DESC
        LIMIT %s, %s
        """,
        args,
    )


async def count_operation_logs(
    settings: Settings,
    *,
    module: str | None,
    action: str | None,
    username: str | None,
    start_at: datetime | None,
    end_at: datetime | None,
) -> int:
    where, args = _build_where(module=module, action=action, username=username, start_at=start_at, end_at=end_at)
    row = await fetch_one(settings, f"SELECT COUNT(*) AS total FROM operation_log {where}", args)
    return int(row["total"]) if row else 0


def _build_where(
    *,
    module: str | None,
    action: str | None,
    username: str | None,
    start_at: datetime | None,
    end_at: datetime | None,
) -> tuple[str, list[Any]]:
    where = []
    args: list[Any] = []
    if module:
        where.append("module = %s")
        args.append(module)
    if action:
        where.append("action = %s")
        args.append(action)
    if username:
        where.append("username LIKE %s")
        args.append(f"%{username}%")
    if start_at:
        where.append("created_at >= %s")
        args.append(start_at)
    if end_at:
        where.append("created_at < %s")
        args.append(end_at)
    return ("WHERE " + " AND ".join(where), args) if where else ("", args)
