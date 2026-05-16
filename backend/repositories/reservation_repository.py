from datetime import date, datetime, time
from typing import Any

import aiomysql

from config.settings import Settings
from repositories import member_repository
from repositories.database import execute, fetch_all, fetch_one, get_pool
from utils.member_levels import discount_rate_for_level, effective_member_level


ACTIVE_STATUSES = ("pending", "confirmed")


RESERVATION_MONEY_COLUMNS = (
    "r.price_per_hour_cents, r.duration_minutes, r.original_amount_cents, "
    "r.discount_amount_cents, r.payable_amount_cents, "
    "r.member_level_snapshot, r.discount_rate, r.points_awarded"
)

RESERVATION_ORDER_COLUMNS = (
    "ro.id AS order_id, ro.order_no, ro.status AS order_status, "
    "ro.amount_cents AS order_amount_cents, ro.pay_method AS order_pay_method, "
    "ro.expires_at AS order_expires_at, ro.paid_at AS order_paid_at, "
    "ro.canceled_at AS order_canceled_at"
)


def _minutes(value: time) -> int:
    return value.hour * 60 + value.minute


async def list_reservations_for_court_date(
    settings: Settings,
    *,
    court_id: int,
    reserve_date: date,
) -> list[dict[str, Any]]:
    return await fetch_all(
        settings,
        """
        SELECT id, reservation_no, user_id, court_id, reserve_date, start_time, end_time, time_slot, status
        FROM reservation
        WHERE court_id = %s AND reserve_date = %s AND status IN ('pending', 'confirmed')
        ORDER BY start_time ASC
        """,
        (court_id, reserve_date),
    )


async def find_conflict(
    settings: Settings,
    *,
    court_id: int,
    reserve_date: date,
    start_time: time,
    end_time: time,
) -> dict[str, Any] | None:
    return await fetch_one(
        settings,
        """
        SELECT id, reservation_no, status
        FROM reservation
        WHERE court_id = %s
          AND reserve_date = %s
          AND status IN ('pending', 'confirmed')
          AND %s < end_time
          AND %s > start_time
        LIMIT 1
        """,
        (court_id, reserve_date, start_time, end_time),
    )


async def count_user_daily_reservations(
    settings: Settings,
    *,
    user_id: int,
    reserve_date: date,
) -> int:
    row = await fetch_one(
        settings,
        """
        SELECT COUNT(*) AS total
        FROM reservation
        WHERE user_id = %s AND reserve_date = %s AND status IN ('pending', 'confirmed')
        """,
        (user_id, reserve_date),
    )
    return int(row["total"]) if row else 0


async def create_reservation(
    settings: Settings,
    *,
    reservation_no: str,
    user_id: int,
    court_id: int,
    reserve_date: date,
    start_time: time,
    end_time: time,
    time_slot: str,
    status: str,
    remark: str,
) -> int:
    return await execute(
        settings,
        """
        INSERT INTO reservation
          (reservation_no, user_id, court_id, reserve_date, start_time, end_time, time_slot, status, remark)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (reservation_no, user_id, court_id, reserve_date, start_time, end_time, time_slot, status, remark),
    )


async def create_pending_reservation_order_atomic(
    settings: Settings,
    *,
    reservation_no: str,
    order_no: str,
    user_id: int,
    court_id: int,
    reserve_date: date,
    start_time: time,
    end_time: time,
    time_slot: str,
    remark: str,
    daily_limit: int,
    expires_at: datetime,
) -> tuple[int | None, int | None, str | None]:
    pool = await get_pool(settings)
    async with pool.acquire() as connection:
        await connection.autocommit(False)
        try:
            await connection.begin()
            async with connection.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute("SELECT id, username, status FROM user WHERE id = %s FOR UPDATE", (user_id,))
                user = await cursor.fetchone()
                if user is None:
                    await connection.rollback()
                    return None, None, "user_not_found"
                if user["status"] != 1:
                    await connection.rollback()
                    return None, None, "user_disabled"

                await cursor.execute(
                    "SELECT id, status, price_per_hour_cents FROM court WHERE id = %s FOR UPDATE",
                    (court_id,),
                )
                court = await cursor.fetchone()
                if court is None:
                    await connection.rollback()
                    return None, None, "court_not_found"
                if court["status"] != 1:
                    await connection.rollback()
                    return None, None, "court_disabled"
                price_per_hour_cents = int(court.get("price_per_hour_cents") or 12000)
                duration_minutes = _minutes(end_time) - _minutes(start_time)
                original_amount_cents = price_per_hour_cents * duration_minutes // 60
                member_account = await member_repository.get_or_create_account_for_update(cursor, user_id)
                member_level_snapshot = effective_member_level(
                    member_account.get("member_level"),
                    member_account.get("expires_at"),
                    reserve_date,
                )
                discount_rate = discount_rate_for_level(member_level_snapshot)
                payable_amount_cents = original_amount_cents * discount_rate // 100
                discount_amount_cents = original_amount_cents - payable_amount_cents
                points_awarded = payable_amount_cents // 100
                balance_before = int(member_account.get("balance_cents") or 0)
                if balance_before < payable_amount_cents:
                    await connection.rollback()
                    return None, None, "insufficient_balance"

                await cursor.execute(
                    """
                    SELECT id
                    FROM reservation
                    WHERE user_id = %s
                      AND reserve_date = %s
                      AND status IN ('pending', 'confirmed')
                    FOR UPDATE
                    """,
                    (user_id, reserve_date),
                )
                user_day_rows = await cursor.fetchall()
                if len(user_day_rows) >= daily_limit:
                    await connection.rollback()
                    return None, None, "daily_limit"

                await cursor.execute(
                    """
                    SELECT id, reservation_no, status
                    FROM reservation
                    WHERE court_id = %s
                      AND reserve_date = %s
                      AND status IN ('pending', 'confirmed')
                      AND %s < end_time
                      AND %s > start_time
                    ORDER BY start_time ASC
                    LIMIT 1
                    FOR UPDATE
                    """,
                    (court_id, reserve_date, start_time, end_time),
                )
                if await cursor.fetchone():
                    await connection.rollback()
                    return None, None, "conflict"

                await cursor.execute(
                    """
                    INSERT INTO reservation
                      (reservation_no, user_id, court_id, reserve_date, start_time, end_time, time_slot, status, remark,
                       price_per_hour_cents, duration_minutes, original_amount_cents, discount_amount_cents,
                       payable_amount_cents, member_level_snapshot, discount_rate, points_awarded)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending', %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        reservation_no,
                        user_id,
                        court_id,
                        reserve_date,
                        start_time,
                        end_time,
                        time_slot,
                        remark,
                        price_per_hour_cents,
                        duration_minutes,
                        original_amount_cents,
                        discount_amount_cents,
                        payable_amount_cents,
                        member_level_snapshot,
                        discount_rate,
                        points_awarded,
                    ),
                )
                reservation_id = int(cursor.lastrowid)
                await cursor.execute(
                    """
                    INSERT INTO reservation_order
                      (order_no, reservation_id, user_id, status, amount_cents, pay_method, expires_at)
                    VALUES (%s, %s, %s, 'pending', %s, 'balance', %s)
                    """,
                    (order_no, reservation_id, user_id, payable_amount_cents, expires_at),
                )
                order_id = int(cursor.lastrowid)
            await connection.commit()
            return reservation_id, order_id, None
        except Exception:
            await connection.rollback()
            raise
        finally:
            await connection.autocommit(True)


async def get_reservation_detail(settings: Settings, reservation_id: int) -> dict[str, Any] | None:
    return await fetch_one(
        settings,
        """
        SELECT r.id, r.reservation_no, r.user_id, u.username, u.nickname,
               r.court_id, c.court_no, c.court_name,
               r.reserve_date, r.start_time, r.end_time, r.time_slot,
               r.status, r.remark, {money_columns}, {order_columns},
               r.created_at, r.updated_at, r.canceled_at
        FROM reservation r
        JOIN user u ON u.id = r.user_id
        JOIN court c ON c.id = r.court_id
        LEFT JOIN reservation_order ro ON ro.reservation_id = r.id
        WHERE r.id = %s
        """.format(money_columns=RESERVATION_MONEY_COLUMNS, order_columns=RESERVATION_ORDER_COLUMNS),
        (reservation_id,),
    )


async def list_user_reservations(
    settings: Settings,
    *,
    user_id: int,
    status: str | None,
    offset: int,
    limit: int,
) -> list[dict[str, Any]]:
    where = ["r.user_id = %s"]
    args: list[Any] = [user_id]
    if status:
        where.append("r.status = %s")
        args.append(status)
    args.extend([offset, limit])
    return await fetch_all(
        settings,
        f"""
        SELECT r.id, r.reservation_no, r.court_id, c.court_no, c.court_name,
               r.reserve_date, r.start_time, r.end_time, r.time_slot,
               r.status, r.remark, {RESERVATION_MONEY_COLUMNS}, {RESERVATION_ORDER_COLUMNS},
               r.created_at, r.canceled_at
        FROM reservation r
        JOIN court c ON c.id = r.court_id
        LEFT JOIN reservation_order ro ON ro.reservation_id = r.id
        WHERE {" AND ".join(where)}
        ORDER BY r.reserve_date DESC, r.start_time DESC, r.id DESC
        LIMIT %s, %s
        """,
        args,
    )


async def count_user_reservations(settings: Settings, *, user_id: int, status: str | None) -> int:
    where = ["user_id = %s"]
    args: list[Any] = [user_id]
    if status:
        where.append("status = %s")
        args.append(status)
    row = await fetch_one(
        settings,
        f"SELECT COUNT(*) AS total FROM reservation WHERE {' AND '.join(where)}",
        args,
    )
    return int(row["total"]) if row else 0


async def count_future_active_reservations_by_user(settings: Settings, *, user_id: int) -> int:
    row = await fetch_one(
        settings,
        """
        SELECT COUNT(*) AS total
        FROM reservation
        WHERE user_id = %s
          AND status IN ('pending', 'confirmed')
          AND (
            reserve_date > CURDATE()
            OR (reserve_date = CURDATE() AND start_time > CURTIME())
          )
        """,
        (user_id,),
    )
    return int(row["total"]) if row else 0


async def count_future_active_reservations_by_court(settings: Settings, *, court_id: int) -> int:
    row = await fetch_one(
        settings,
        """
        SELECT COUNT(*) AS total
        FROM reservation
        WHERE court_id = %s
          AND status IN ('pending', 'confirmed')
          AND (
            reserve_date > CURDATE()
            OR (reserve_date = CURDATE() AND start_time > CURTIME())
          )
        """,
        (court_id,),
    )
    return int(row["total"]) if row else 0


async def list_admin_reservations(
    settings: Settings,
    *,
    status: str | None,
    username: str | None,
    court_id: int | None,
    date_from: date | None,
    date_to: date | None,
    offset: int,
    limit: int,
) -> list[dict[str, Any]]:
    where = []
    args: list[Any] = []
    if status:
        where.append("r.status = %s")
        args.append(status)
    if username:
        where.append("(u.username LIKE %s OR u.nickname LIKE %s)")
        args.extend([f"%{username}%", f"%{username}%"])
    if court_id:
        where.append("r.court_id = %s")
        args.append(court_id)
    if date_from:
        where.append("r.reserve_date >= %s")
        args.append(date_from)
    if date_to:
        where.append("r.reserve_date <= %s")
        args.append(date_to)
    where_sql = "WHERE " + " AND ".join(where) if where else ""
    args.extend([offset, limit])
    return await fetch_all(
        settings,
        f"""
        SELECT r.id, r.reservation_no, r.user_id, u.username, u.nickname,
               r.court_id, c.court_no, c.court_name,
               r.reserve_date, r.start_time, r.end_time, r.time_slot,
               r.status, r.remark, {RESERVATION_MONEY_COLUMNS}, {RESERVATION_ORDER_COLUMNS},
               r.created_at, r.canceled_at
        FROM reservation r
        JOIN user u ON u.id = r.user_id
        JOIN court c ON c.id = r.court_id
        LEFT JOIN reservation_order ro ON ro.reservation_id = r.id
        {where_sql}
        ORDER BY r.reserve_date DESC, r.start_time DESC, r.id DESC
        LIMIT %s, %s
        """,
        args,
    )


async def count_admin_reservations(settings: Settings, *, status: str | None) -> int:
    return await count_admin_reservations_filtered(
        settings,
        status=status,
        username=None,
        court_id=None,
        date_from=None,
        date_to=None,
    )


async def count_admin_reservations_filtered(
    settings: Settings,
    *,
    status: str | None,
    username: str | None,
    court_id: int | None,
    date_from: date | None,
    date_to: date | None,
) -> int:
    where = []
    args: list[Any] = []
    if status:
        where.append("r.status = %s")
        args.append(status)
    if username:
        where.append("(u.username LIKE %s OR u.nickname LIKE %s)")
        args.extend([f"%{username}%", f"%{username}%"])
    if court_id:
        where.append("r.court_id = %s")
        args.append(court_id)
    if date_from:
        where.append("r.reserve_date >= %s")
        args.append(date_from)
    if date_to:
        where.append("r.reserve_date <= %s")
        args.append(date_to)
    where_sql = "WHERE " + " AND ".join(where) if where else ""
    row = await fetch_one(
        settings,
        f"""
        SELECT COUNT(*) AS total
        FROM reservation r
        JOIN user u ON u.id = r.user_id
        {where_sql}
        """,
        args,
    )
    return int(row["total"]) if row else 0


async def cancel_reservation(settings: Settings, reservation_id: int) -> None:
    await execute(
        settings,
        "UPDATE reservation SET status = 'canceled', canceled_at = NOW() WHERE id = %s",
        (reservation_id,),
    )


async def expire_pending_reservation_orders(settings: Settings) -> int:
    return await execute(
        settings,
        """
        UPDATE reservation_order ro
        JOIN reservation r ON r.id = ro.reservation_id
        SET ro.status = 'expired',
            r.status = 'expired'
        WHERE ro.status = 'pending'
          AND r.status = 'pending'
          AND ro.expires_at <= NOW()
        """,
    )


async def pay_reservation_order_atomic(
    settings: Settings,
    *,
    order_id: int,
    user_id: int,
    operator_username: str | None,
) -> tuple[int | None, str | None]:
    pool = await get_pool(settings)
    async with pool.acquire() as connection:
        await connection.autocommit(False)
        try:
            await connection.begin()
            async with connection.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    """
                    SELECT ro.id AS order_id, ro.order_no, ro.user_id, ro.status AS order_status,
                           ro.amount_cents, ro.expires_at,
                           r.id AS reservation_id, r.reservation_no, r.status AS reservation_status,
                           r.payable_amount_cents, r.points_awarded
                    FROM reservation_order ro
                    JOIN reservation r ON r.id = ro.reservation_id
                    WHERE ro.id = %s AND ro.user_id = %s
                    FOR UPDATE
                    """,
                    (order_id, user_id),
                )
                order = await cursor.fetchone()
                if order is None:
                    await connection.rollback()
                    return None, "not_found"

                if order["order_status"] == "expired" or order["reservation_status"] == "expired":
                    await connection.rollback()
                    return None, "expired"
                if order["order_status"] != "pending":
                    await connection.rollback()
                    return None, "not_pending"
                if order["reservation_status"] != "pending":
                    await connection.rollback()
                    return None, "reservation_not_pending"
                expires_at = order.get("expires_at")
                if expires_at and datetime.now() >= expires_at:
                    await cursor.execute("UPDATE reservation_order SET status = 'expired' WHERE id = %s", (order_id,))
                    await cursor.execute(
                        "UPDATE reservation SET status = 'expired' WHERE id = %s",
                        (order["reservation_id"],),
                    )
                    await connection.commit()
                    return None, "expired"

                await cursor.execute("SELECT id, username, status FROM user WHERE id = %s FOR UPDATE", (user_id,))
                user = await cursor.fetchone()
                if user is None:
                    await connection.rollback()
                    return None, "user_not_found"
                if user["status"] != 1:
                    await connection.rollback()
                    return None, "user_disabled"

                amount_cents = int(order.get("amount_cents") or order.get("payable_amount_cents") or 0)
                points_awarded = int(order.get("points_awarded") or 0)
                account = await member_repository.get_or_create_account_for_update(cursor, user_id)
                balance_before = int(account.get("balance_cents") or 0)
                points_before = int(account.get("points") or 0)
                if balance_before < amount_cents:
                    await connection.rollback()
                    return None, "insufficient_balance"
                balance_after = balance_before - amount_cents
                points_after = points_before + points_awarded

                await cursor.execute(
                    "UPDATE member_account SET balance_cents = %s, points = %s WHERE user_id = %s",
                    (balance_after, points_after, user_id),
                )
                await cursor.execute(
                    "UPDATE reservation SET status = 'confirmed' WHERE id = %s AND status = 'pending'",
                    (order["reservation_id"],),
                )
                if cursor.rowcount != 1:
                    await connection.rollback()
                    return None, "reservation_not_pending"
                await cursor.execute(
                    """
                    UPDATE reservation_order
                    SET status = 'paid', paid_at = NOW()
                    WHERE id = %s AND status = 'pending'
                    """,
                    (order_id,),
                )
                if cursor.rowcount != 1:
                    await connection.rollback()
                    return None, "not_pending"
                await member_repository.insert_member_transaction_with_cursor(
                    cursor,
                    user_id=user_id,
                    reservation_id=int(order["reservation_id"]),
                    transaction_type="reservation_charge",
                    balance_change_cents=-amount_cents,
                    points_change=points_awarded,
                    balance_before_cents=balance_before,
                    balance_after_cents=balance_after,
                    points_before=points_before,
                    points_after=points_after,
                    reason=f"预约支付 {order['reservation_no']}",
                    operator_id=user_id,
                    operator_username=operator_username or user.get("username"),
                )
            await connection.commit()
            return int(order["reservation_id"]), None
        except Exception:
            await connection.rollback()
            raise
        finally:
            await connection.autocommit(True)


async def cancel_reservation_atomic(
    settings: Settings,
    reservation_id: int,
    *,
    operator_id: int | None,
    operator_username: str | None,
    reason: str,
) -> tuple[int | None, str | None, int]:
    pool = await get_pool(settings)
    async with pool.acquire() as connection:
        await connection.autocommit(False)
        try:
            await connection.begin()
            async with connection.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    """
                    SELECT r.id, r.reservation_no, r.user_id, r.status, r.payable_amount_cents, r.points_awarded,
                           ro.id AS order_id, ro.status AS order_status, ro.paid_at AS order_paid_at
                    FROM reservation r
                    LEFT JOIN reservation_order ro ON ro.reservation_id = r.id
                    WHERE r.id = %s
                    FOR UPDATE
                    """,
                    (reservation_id,),
                )
                reservation = await cursor.fetchone()
                if reservation is None:
                    await connection.rollback()
                    return None, "not_found", 0
                if reservation["status"] == "pending":
                    await cursor.execute(
                        "UPDATE reservation SET status = 'canceled', canceled_at = NOW() WHERE id = %s",
                        (reservation_id,),
                    )
                    if reservation.get("order_id") and reservation.get("order_status") == "pending":
                        await cursor.execute(
                            """
                            UPDATE reservation_order
                            SET status = 'canceled', canceled_at = NOW(), cancel_reason = %s
                            WHERE id = %s
                            """,
                            (reason, reservation["order_id"]),
                        )
                    await connection.commit()
                    return reservation_id, None, 0
                if reservation["status"] != "confirmed":
                    await connection.rollback()
                    return None, "not_confirmed", 0

                user_id = int(reservation["user_id"])
                member_account = await member_repository.get_or_create_account_for_update(cursor, user_id)
                balance_before = int(member_account.get("balance_cents") or 0)
                points_before = int(member_account.get("points") or 0)
                refund_cents = int(reservation.get("payable_amount_cents") or 0)
                points_awarded = int(reservation.get("points_awarded") or 0)
                points_revoke = min(points_awarded, points_before)
                balance_after = balance_before + refund_cents
                points_after = points_before - points_revoke

                await cursor.execute(
                    "UPDATE reservation SET status = 'canceled', canceled_at = NOW() WHERE id = %s",
                    (reservation_id,),
                )
                if reservation.get("order_id") and reservation.get("order_status") == "paid":
                    await cursor.execute(
                        """
                        UPDATE reservation_order
                        SET status = 'canceled', canceled_at = NOW(), cancel_reason = %s
                        WHERE id = %s
                        """,
                        (reason, reservation["order_id"]),
                    )
                await cursor.execute(
                    "UPDATE member_account SET balance_cents = %s, points = %s WHERE user_id = %s",
                    (balance_after, points_after, user_id),
                )
                await member_repository.insert_member_transaction_with_cursor(
                    cursor,
                    user_id=user_id,
                    reservation_id=reservation_id,
                    transaction_type="reservation_refund",
                    balance_change_cents=refund_cents,
                    points_change=-points_revoke,
                    balance_before_cents=balance_before,
                    balance_after_cents=balance_after,
                    points_before=points_before,
                    points_after=points_after,
                    reason=reason,
                    operator_id=operator_id,
                    operator_username=operator_username,
                )
            await connection.commit()
            return reservation_id, None, refund_cents
        except Exception:
            await connection.rollback()
            raise
        finally:
            await connection.autocommit(True)


async def complete_finished_reservations(settings: Settings) -> int:
    return await execute(
        settings,
        """
        UPDATE reservation
        SET status = 'completed'
        WHERE status = 'confirmed'
          AND (
            reserve_date < CURDATE()
            OR (reserve_date = CURDATE() AND end_time <= CURTIME())
          )
        """,
    )
