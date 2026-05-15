import redis.asyncio as redis

from config.settings import Settings


def get_redis_client(settings: Settings) -> redis.Redis:
    return redis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
        decode_responses=True,
    )


def reservation_lock_key(court_id: int, reserve_date: str, start_time: str, end_time: str) -> str:
    return f"reservation:lock:{court_id}:{reserve_date}:{start_time}:{end_time}"


async def acquire_lock(settings: Settings, key: str, value: str, ttl_seconds: int) -> bool:
    client = get_redis_client(settings)
    try:
        return bool(await client.set(key, value, nx=True, ex=ttl_seconds))
    finally:
        await client.aclose()


async def release_lock(settings: Settings, key: str, value: str) -> None:
    client = get_redis_client(settings)
    try:
        current_value = await client.get(key)
        if current_value == value:
            await client.delete(key)
    finally:
        await client.aclose()


async def lock_exists(settings: Settings, key: str) -> bool:
    client = get_redis_client(settings)
    try:
        return bool(await client.exists(key))
    finally:
        await client.aclose()
