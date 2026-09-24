from datetime import date, datetime, time
from typing import Any

import aiomysql

from config.settings import Settings
from repositories import member_repository, booking_operations_repository
from repositories.database import execute, fetch_all, fetch_one, get_pool
from utils.member_levels import discount_rate_for_level, effective_member_level


ACTIVE_STATUSES = ("pending", "confirmed")


RESERVATION_OPERATIONS_COLUMNS = (
    "(SELECT outcome FROM reservation_attendance WHERE reservation_id=r.id) AS attendance_outcome, "
    "(SELECT recorded_at FROM reservation_attendance WHERE reservation_id=r.id) AS attendance_recorded_at, "
    "(SELECT recorded_by FROM reservation_attendance WHERE reservation_id=r.id) AS attendance_recorded_by, "
    "(SELECT COALESCE(MAX(id),0) FROM reservation_change WHERE reservation_id=r.id) AS revision"
)

RESERVATION_MONEY_COLUMNS = (
    "r.source, r.operator_id, r.operator_name_snapshot, r.guest_name, r.guest_contact, "
    "r.opened_at, r.parent_reservation_id, r.root_reservation_id, "
    "r.price_per_hour_cents, r.duration_minutes, r.original_amount_cents, "
    "r.discount_amount_cents, r.payable_amount_cents, "
    "r.member_level_snapshot, r.discount_rate, r.points_awarded, " + RESERVATION_OPERATIONS_COLUMNS
)

RESERVATION_ORDER_COLUMNS = (
    "(SELECT id FROM payment_order WHERE reservation_order_id=ro.id AND purpose='initial' LIMIT 1) AS payment_id, "
    "(SELECT MAX(id) FROM payment_order WHERE reservation_order_id=ro.id AND purpose='reschedule' AND status='pending' AND expires_at>NOW()) AS reschedule_payment_id, "
    "ro.id AS order_id, ro.order_no, ro.status AS order_status, "
    "ro.amount_cents AS order_amount_cents, ro.pay_method AS order_pay_method, "
    "ro.expires_at AS order_expires_at, ro.paid_at AS order_paid_at, "
    "ro.canceled_at AS order_canceled_at"
)


def _minutes(value: time) -> int:
    return value.hour * 60 + value.minute


async def get_user_summary(settings: Settings, *, user_id: int) -> dict[str, Any]:
    # Query the complete history, not a recent page: the earliest future booking
    # can be on a later page when the usual list is sorted newest first.
    columns = f"""
        SELECT r.*, c.court_no, c.court_name, {RESERVATION_OPERATIONS_COLUMNS}, {RESERVATION_ORDER_COLUMNS}
        FROM reservation r JOIN court c ON c.id = r.court_id
        LEFT JOIN reservation_order ro ON ro.reservation_id = r.id
    """
    upcoming = await fetch_one(settings, columns + """
        WHERE r.user_id = %s AND r.status = 'confirmed'
          AND TIMESTAMP(r.reserve_date, r.end_time) > NOW()
        ORDER BY r.reserve_date, r.start_time, r.id LIMIT 1
    """, (user_id,))
    pending_where = """
        WHERE r.user_id = %s AND r.status = 'pending'
          AND ro.status = 'pending' AND ro.expires_at > NOW()
    """
    pending = await fetch_one(settings, columns + pending_where +
                             " ORDER BY ro.expires_at, r.id LIMIT 1", (user_id,))
    count = await fetch_one(settings, """
        SELECT COUNT(*) AS total FROM reservation r
        JOIN reservation_order ro ON ro.reservation_id = r.id
    """ + pending_where, (user_id,))
    return {"upcoming": upcoming, "pending": pending,
            "pending_count": int(count["total"]) if count else 0}


async def list_reservations_for_court_date(
    settings: Settings,
    *,
    court_id: int,
    reserve_date: date,
) -> list[dict[str, Any]]:
    return await fetch_all(
        settings,
        """
        SELECT r.id, r.reservation_no, r.user_id, r.court_id, r.reserve_date, r.start_time, r.end_time, r.time_slot, r.status
        FROM reservation r LEFT JOIN reservation_order ro ON ro.reservation_id=r.id
        WHERE r.court_id = %s AND r.reserve_date = %s
          AND (r.status='confirmed' OR (r.status='pending' AND ro.status='pending' AND ro.expires_at>NOW()))
        ORDER BY r.start_time ASC
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
        SELECT r.id, r.reservation_no, r.status
        FROM reservation r LEFT JOIN reservation_order ro ON ro.reservation_id=r.id
        WHERE r.court_id = %s
          AND r.reserve_date = %s
          AND (r.status='confirmed' OR (r.status='pending' AND ro.status='pending' AND ro.expires_at>NOW()))
          AND %s < r.end_time
          AND %s > r.start_time
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
    expected_amount_cents: int | None = None,
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
                if await booking_operations_repository.blocked(cursor, {
                    'court_id': court_id, 'reserve_date': reserve_date, 'start_time': start_time, 'end_time': end_time,
                }):
                    await connection.rollback()
                    return None, None, "maintenance"
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
                if expected_amount_cents is not None and payable_amount_cents != expected_amount_cents:
                    await connection.rollback()
                    return None, None, 'price_changed'
                balance_before = int(member_account.get("balance_cents") or 0)
                from repositories.balance_holds import held_balance
                pending_amount_cents = await held_balance(cursor,user_id)
                available_balance_cents = balance_before - pending_amount_cents
                if available_balance_cents < payable_amount_cents:
                    await connection.rollback()
                    return None, None, "insufficient_available_balance"

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
        LEFT JOIN user u ON u.id = r.user_id
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
          AND r.source = 'online'
          AND NOT EXISTS (SELECT 1 FROM payment_order p WHERE p.reservation_order_id=ro.id)
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
                await cursor.execute("SELECT id FROM user WHERE id=%s FOR UPDATE", (user_id,))
                await cursor.execute(
                    """
                    SELECT ro.id AS order_id, ro.order_no, ro.user_id, ro.status AS order_status,
                           ro.amount_cents, ro.expires_at, ro.pay_method,
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

                if order['pay_method'] != 'balance':
                    await connection.rollback()
                    return None, 'wrong_channel'
                amount_cents = int(order.get("amount_cents") or order.get("payable_amount_cents") or 0)
                points_awarded = int(order.get("points_awarded") or 0)
                account = await member_repository.get_or_create_account_for_update(cursor, user_id)
                balance_before = int(account.get("balance_cents") or 0)
                points_before = int(account.get("points") or 0)
                from repositories.balance_holds import held_balance
                held = await held_balance(cursor,user_id,reservation_order_id=order_id)
                if balance_before - held < amount_cents:
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
    require_future: bool = False,
) -> tuple[int | None, str | None, int]:
    pool = await get_pool(settings)
    async with pool.acquire() as connection:
        await connection.autocommit(False)
        try:
            await connection.begin()
            async with connection.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute("SELECT user_id FROM reservation WHERE id=%s", (reservation_id,))
                owner = await cursor.fetchone()
                if owner is None:
                    await connection.rollback()
                    return None, "not_found", 0
                await cursor.execute("SELECT id FROM user WHERE id=%s FOR UPDATE", (owner['user_id'],))
                await cursor.execute(
                    """
                    SELECT r.id, r.reservation_no, r.user_id, r.status, r.reserve_date, r.start_time, r.payable_amount_cents, r.points_awarded,
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
                await cursor.execute("SELECT reservation_id FROM reservation_attendance WHERE reservation_id=%s FOR UPDATE", (reservation_id,))
                if await cursor.fetchone():
                    await connection.rollback()
                    return None, "attendance_recorded", 0
                if require_future:
                    from utils.booking_operations import at
                    if at(reservation['reserve_date'], reservation['start_time']) <= datetime.now():
                        await connection.rollback()
                        return None, "already_started", 0
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
