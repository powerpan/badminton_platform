from datetime import date
from typing import Any

import aiomysql

from config.settings import Settings
from repositories.database import execute, fetch_one, get_pool
from utils.member_levels import DEFAULT_MEMBER_LEVEL


MEMBER_ACCOUNT_COLUMNS = """
    user_id, member_level, balance_cents, points, expires_at, created_at, updated_at
"""


async def create_default_member_account(settings: Settings, user_id: int) -> None:
    await execute(
        settings,
        """
        INSERT INTO member_account (user_id, member_level, balance_cents, points, expires_at)
        VALUES (%s, %s, 0, 0, NULL)
        ON DUPLICATE KEY UPDATE user_id = VALUES(user_id)
        """,
        (user_id, DEFAULT_MEMBER_LEVEL),
    )


async def get_member_account(settings: Settings, user_id: int) -> dict[str, Any] | None:
    return await fetch_one(
        settings,
        f"SELECT {MEMBER_ACCOUNT_COLUMNS} FROM member_account WHERE user_id = %s",
        (user_id,),
    )


async def get_or_create_account_for_update(cursor: aiomysql.DictCursor, user_id: int) -> dict[str, Any]:
    await cursor.execute(
        f"SELECT {MEMBER_ACCOUNT_COLUMNS} FROM member_account WHERE user_id = %s FOR UPDATE",
        (user_id,),
    )
    account = await cursor.fetchone()
    if account is not None:
        return account

    await cursor.execute(
        """
        INSERT INTO member_account (user_id, member_level, balance_cents, points, expires_at)
        VALUES (%s, %s, 0, 0, NULL)
        """,
        (user_id, DEFAULT_MEMBER_LEVEL),
    )
    await cursor.execute(
        f"SELECT {MEMBER_ACCOUNT_COLUMNS} FROM member_account WHERE user_id = %s FOR UPDATE",
        (user_id,),
    )
    account = await cursor.fetchone()
    if account is None:
        raise RuntimeError("member account create failed")
    return account


async def insert_member_transaction_with_cursor(
    cursor: aiomysql.DictCursor,
    *,
    user_id: int,
    reservation_id: int | None,
    transaction_type: str,
    balance_change_cents: int,
    points_change: int,
    balance_before_cents: int,
    balance_after_cents: int,
    points_before: int,
    points_after: int,
    reason: str,
    operator_id: int | None,
    operator_username: str | None,
) -> None:
    await cursor.execute(
        """
        INSERT INTO member_account_transaction
          (user_id, reservation_id, transaction_type, balance_change_cents, points_change,
           balance_before_cents, balance_after_cents, points_before, points_after,
           reason, operator_id, operator_username)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            user_id,
            reservation_id,
            transaction_type,
            balance_change_cents,
            points_change,
            balance_before_cents,
            balance_after_cents,
            points_before,
            points_after,
            reason,
            operator_id,
            operator_username,
        ),
    )


async def adjust_member_account_atomic(
    settings: Settings,
    *,
    user_id: int,
    member_level: str,
    expires_at: date | None,
    balance_change_cents: int,
    points_change: int,
    reason: str,
    operator_id: int | None,
    operator_username: str | None,
) -> tuple[dict[str, Any] | None, str | None]:
    pool = await get_pool(settings)
    async with pool.acquire() as connection:
        await connection.autocommit(False)
        try:
            await connection.begin()
            async with connection.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute("SELECT id FROM user WHERE id = %s FOR UPDATE", (user_id,))
                if await cursor.fetchone() is None:
                    await connection.rollback()
                    return None, "user_not_found"

                account = await get_or_create_account_for_update(cursor, user_id)
                balance_before = int(account.get("balance_cents") or 0)
                points_before = int(account.get("points") or 0)
                balance_after = balance_before + balance_change_cents
                points_after = points_before + points_change
                if balance_after < 0:
                    await connection.rollback()
                    return None, "insufficient_balance"
                if points_after < 0:
                    await connection.rollback()
                    return None, "insufficient_points"

                await cursor.execute(
                    """
                    UPDATE member_account
                    SET member_level = %s,
                        balance_cents = %s,
                        points = %s,
                        expires_at = %s
                    WHERE user_id = %s
                    """,
                    (member_level, balance_after, points_after, expires_at, user_id),
                )
                await insert_member_transaction_with_cursor(
                    cursor,
                    user_id=user_id,
                    reservation_id=None,
                    transaction_type="admin_adjust",
                    balance_change_cents=balance_change_cents,
                    points_change=points_change,
                    balance_before_cents=balance_before,
                    balance_after_cents=balance_after,
                    points_before=points_before,
                    points_after=points_after,
                    reason=reason,
                    operator_id=operator_id,
                    operator_username=operator_username,
                )
                await cursor.execute(
                    f"SELECT {MEMBER_ACCOUNT_COLUMNS} FROM member_account WHERE user_id = %s",
                    (user_id,),
                )
                updated = await cursor.fetchone()
            await connection.commit()
            return updated, None
        except Exception:
            await connection.rollback()
            raise
        finally:
            await connection.autocommit(True)
