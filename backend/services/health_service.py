from typing import Any

from config.settings import Settings


async def check_mysql(settings: Settings) -> dict[str, Any]:
    try:
        import aiomysql

        connection = await aiomysql.connect(
            host=settings.mysql_host,
            port=settings.mysql_port,
            user=settings.mysql_user,
            password=settings.mysql_password,
            db=settings.mysql_database,
            autocommit=True,
        )
        try:
            async with connection.cursor() as cursor:
                await cursor.execute("SELECT 1")
                await cursor.fetchone()
        finally:
            connection.close()
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


async def check_redis(settings: Settings) -> dict[str, Any]:
    try:
        import redis.asyncio as redis

        client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            decode_responses=True,
        )
        try:
            await client.ping()
        finally:
            await client.aclose()
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


async def collect_health(settings: Settings) -> dict[str, Any]:
    mysql = await check_mysql(settings)
    redis = await check_redis(settings)
    return {
        "api": {"status": "ok"},
        "mysql": mysql,
        "redis": redis,
        "env": settings.app_env,
    }
