import redis.asyncio as redis

from config.settings import Settings


RELEASE_LOCK_SCRIPT = """
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
end
return 0
"""


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
        await client.eval(RELEASE_LOCK_SCRIPT, 1, key, value)
    finally:
        await client.aclose()


async def lock_exists(settings: Settings, key: str) -> bool:
    client = get_redis_client(settings)
    try:
        return bool(await client.exists(key))
    finally:
        await client.aclose()


async def set_value(settings: Settings, key: str, value: str, ttl_seconds: int) -> None:
    client = get_redis_client(settings)
    try:
        await client.set(key, value, ex=ttl_seconds)
    finally:
        await client.aclose()


async def get_value(settings: Settings, key: str) -> str | None:
    client = get_redis_client(settings)
    try:
        value = await client.get(key)
        return str(value) if value is not None else None
    finally:
        await client.aclose()


async def delete_keys(settings: Settings, *keys: str) -> None:
    if not keys:
        return
    client = get_redis_client(settings)
    try:
        await client.delete(*keys)
    finally:
        await client.aclose()


async def delete_pattern(settings: Settings, pattern: str) -> int:
    client = get_redis_client(settings)
    deleted = 0
    batch: list[str] = []
    try:
        async for key in client.scan_iter(match=pattern, count=100):
            batch.append(str(key))
            if len(batch) >= 200:
                deleted += int(await client.delete(*batch))
                batch.clear()
        if batch:
            deleted += int(await client.delete(*batch))
        return deleted
    finally:
        await client.aclose()


async def increment_with_ttl(settings: Settings, key: str, ttl_seconds: int) -> int:
    client = get_redis_client(settings)
    try:
        value = await client.incr(key)
        if value == 1:
            await client.expire(key, ttl_seconds)
        return int(value)
    finally:
        await client.aclose()


async def ttl(settings: Settings, key: str) -> int:
    client = get_redis_client(settings)
    try:
        return int(await client.ttl(key))
    finally:
        await client.aclose()
