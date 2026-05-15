from collections.abc import Sequence
from typing import Any

import aiomysql

from config.settings import Settings


_pool: aiomysql.Pool | None = None


async def get_pool(settings: Settings) -> aiomysql.Pool:
    global _pool
    if _pool is None or _pool.closed:
        _pool = await aiomysql.create_pool(
            host=settings.mysql_host,
            port=settings.mysql_port,
            user=settings.mysql_user,
            password=settings.mysql_password,
            db=settings.mysql_database,
            minsize=1,
            maxsize=10,
            autocommit=True,
        )
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None and not _pool.closed:
        _pool.close()
        await _pool.wait_closed()
    _pool = None


async def fetch_one(settings: Settings, sql: str, args: Sequence[Any] = ()) -> dict[str, Any] | None:
    pool = await get_pool(settings)
    async with pool.acquire() as connection:
        async with connection.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute(sql, args)
            return await cursor.fetchone()


async def fetch_all(settings: Settings, sql: str, args: Sequence[Any] = ()) -> list[dict[str, Any]]:
    pool = await get_pool(settings)
    async with pool.acquire() as connection:
        async with connection.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute(sql, args)
            rows = await cursor.fetchall()
            return list(rows)


async def execute(settings: Settings, sql: str, args: Sequence[Any] = ()) -> int:
    pool = await get_pool(settings)
    async with pool.acquire() as connection:
        async with connection.cursor() as cursor:
            await cursor.execute(sql, args)
            return cursor.lastrowid or cursor.rowcount
