"""Shared transaction and audit boundary for booking and staff payment workflows."""
import json
from contextlib import asynccontextmanager
import aiomysql
from repositories.database import get_pool
from utils.response import ApiError


@asynccontextmanager
async def transaction(settings, *, read_only=False):
    pool = await get_pool(settings)
    async with pool.acquire() as connection:
        await connection.autocommit(False)
        try:
            if read_only:
                async with connection.cursor() as setup:
                    await setup.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
                    await setup.execute('START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY')
            else:
                await connection.begin()
            async with connection.cursor(aiomysql.DictCursor) as cursor:
                yield cursor
            await connection.commit()
        except aiomysql.OperationalError as exc:
            await connection.rollback()
            if exc.args[0] in (1205, 1213):
                raise ApiError(409, '当前记录正在处理中，请刷新后重试', 409) from exc
            raise
        except BaseException:
            await connection.rollback()
            raise
        finally:
            await connection.autocommit(True)


async def audit(cursor, actor, module, action, target_id, detail):
    await cursor.execute('''INSERT INTO operation_log
        (user_id, username, role, module, action, target_type, target_id, detail)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)''',
        (actor['id'], actor.get('username'), actor.get('role', 'user'), module, action, module, target_id,
         json.dumps(detail, ensure_ascii=False, default=str)))
