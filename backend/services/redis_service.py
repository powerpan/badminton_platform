import redis.asyncio as redis

from config.settings import Settings


RELEASE_LOCK_SCRIPT = """
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
end
return 0
"""


_clients: dict[tuple[str, int, int], redis.Redis] = {}


def get_redis_client(settings: Settings) -> redis.Redis:
    key = (settings.redis_host, settings.redis_port, settings.redis_db)
    if key not in _clients:
        _clients[key] = redis.Redis(
            host=key[0], port=key[1], db=key[2], decode_responses=True,
            socket_connect_timeout=3, socket_timeout=3,
        )
    return _clients[key]


async def close_redis_clients() -> None:
    clients = list(_clients.values())
    _clients.clear()
    for client in clients:
        await client.aclose()


async def locks_exist(settings: Settings, keys: list[str]) -> list[bool]:
    if not keys:
        return []
    # One round trip and a reusable connection instead of one connection per slot.
    values = await get_redis_client(settings).mget(keys)
    return [value is not None for value in values]


def reservation_lock_key(court_id: int, reserve_date: str, start_time: str, end_time: str) -> str:
    return f"reservation:lock:{court_id}:{reserve_date}:{start_time}:{end_time}"


async def acquire_lock(settings: Settings, key: str, value: str, ttl_seconds: int) -> bool:
    client = get_redis_client(settings)
    return bool(await client.set(key, value, nx=True, ex=ttl_seconds))


async def release_lock(settings: Settings, key: str, value: str) -> None:
    client = get_redis_client(settings)
    await client.eval(RELEASE_LOCK_SCRIPT, 1, key, value)


async def lock_exists(settings: Settings, key: str) -> bool:
    client = get_redis_client(settings)
    return bool(await client.exists(key))


async def set_value(settings: Settings, key: str, value: str, ttl_seconds: int) -> None:
    client = get_redis_client(settings)
    await client.set(key, value, ex=ttl_seconds)


async def get_value(settings: Settings, key: str) -> str | None:
    client = get_redis_client(settings)
    value = await client.get(key)
    return str(value) if value is not None else None


async def delete_keys(settings: Settings, *keys: str) -> None:
    if not keys:
        return
    client = get_redis_client(settings)
    await client.delete(*keys)


async def delete_pattern(settings: Settings, pattern: str) -> int:
    client = get_redis_client(settings)
    deleted = 0
    batch: list[str] = []
    async for key in client.scan_iter(match=pattern, count=100):
        batch.append(str(key))
        if len(batch) >= 200:
            deleted += int(await client.delete(*batch))
            batch.clear()
    if batch:
        deleted += int(await client.delete(*batch))
    return deleted


async def increment_with_ttl(settings: Settings, key: str, ttl_seconds: int) -> int:
    client = get_redis_client(settings)
    value = await client.incr(key)
    if value == 1:
        await client.expire(key, ttl_seconds)
    return int(value)


async def ttl(settings: Settings, key: str) -> int:
    client = get_redis_client(settings)
    return int(await client.ttl(key))
