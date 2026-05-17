from typing import Any

import aiomysql

from config.settings import Settings
from repositories import member_repository
from repositories.database import execute, fetch_all, fetch_one, get_pool


PRODUCT_COLUMNS = (
    "id, product_no, product_name, description, image_url, price_cents, stock, sold_count, "
    "status, created_at, updated_at"
)

ORDER_COLUMNS = (
    "o.id, o.order_no, o.user_id, u.username, u.nickname, o.status, o.total_amount_cents, "
    "o.pay_method, o.paid_at, o.completed_at, o.canceled_at, o.cancel_reason, o.remark, "
    "o.refund_requested_at, o.refund_request_reason, o.refund_reviewed_at, o.refund_reject_reason, "
    "o.created_at, o.updated_at"
)

ORDER_ITEM_COLUMNS = (
    "id, order_id, product_id, product_no_snapshot, product_name_snapshot, image_url_snapshot, "
    "price_cents, quantity, subtotal_cents, created_at"
)


async def list_products(
    settings: Settings,
    *,
    status: int | None,
    keyword: str | None,
    offset: int,
    limit: int,
) -> list[dict[str, Any]]:
    where = []
    args: list[Any] = []
    if status is not None:
        where.append("status = %s")
        args.append(status)
    if keyword:
        where.append("(product_no LIKE %s OR product_name LIKE %s)")
        args.extend([f"%{keyword}%", f"%{keyword}%"])
    where_sql = "WHERE " + " AND ".join(where) if where else ""
    args.extend([offset, limit])
    return await fetch_all(
        settings,
        f"""
        SELECT {PRODUCT_COLUMNS}
        FROM shop_product
        {where_sql}
        ORDER BY status DESC, id DESC
        LIMIT %s, %s
        """,
        args,
    )


async def count_products(settings: Settings, *, status: int | None, keyword: str | None) -> int:
    where = []
    args: list[Any] = []
    if status is not None:
        where.append("status = %s")
        args.append(status)
    if keyword:
        where.append("(product_no LIKE %s OR product_name LIKE %s)")
        args.extend([f"%{keyword}%", f"%{keyword}%"])
    where_sql = "WHERE " + " AND ".join(where) if where else ""
    row = await fetch_one(settings, f"SELECT COUNT(*) AS total FROM shop_product {where_sql}", args)
    return int(row["total"]) if row else 0


async def get_product(settings: Settings, product_id: int) -> dict[str, Any] | None:
    return await fetch_one(settings, f"SELECT {PRODUCT_COLUMNS} FROM shop_product WHERE id = %s", (product_id,))


async def get_product_by_no(settings: Settings, product_no: str) -> dict[str, Any] | None:
    return await fetch_one(settings, f"SELECT {PRODUCT_COLUMNS} FROM shop_product WHERE product_no = %s", (product_no,))


async def create_product(
    settings: Settings,
    *,
    product_no: str,
    product_name: str,
    description: str,
    image_url: str,
    price_cents: int,
    stock: int,
    status: int,
) -> int:
    return await execute(
        settings,
        """
        INSERT INTO shop_product
          (product_no, product_name, description, image_url, price_cents, stock, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (product_no, product_name, description, image_url, price_cents, stock, status),
    )


async def update_product(
    settings: Settings,
    *,
    product_id: int,
    product_no: str,
    product_name: str,
    description: str,
    image_url: str,
    price_cents: int,
    stock: int,
    status: int,
) -> None:
    await execute(
        settings,
        """
        UPDATE shop_product
        SET product_no = %s,
            product_name = %s,
            description = %s,
            image_url = %s,
            price_cents = %s,
            stock = %s,
            status = %s
        WHERE id = %s
        """,
        (product_no, product_name, description, image_url, price_cents, stock, status, product_id),
    )


async def update_product_status(settings: Settings, product_id: int, status: int) -> None:
    await execute(settings, "UPDATE shop_product SET status = %s WHERE id = %s", (status, product_id))


async def create_paid_order_atomic(
    settings: Settings,
    *,
    order_no: str,
    user_id: int,
    items: list[dict[str, int]],
    remark: str,
) -> tuple[int | None, str | None]:
    product_ids = [item["product_id"] for item in items]
    quantity_by_product = {item["product_id"]: item["quantity"] for item in items}
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
                    return None, "user_not_found"
                if user["status"] != 1:
                    await connection.rollback()
                    return None, "user_disabled"

                placeholders = ",".join(["%s"] * len(product_ids))
                await cursor.execute(
                    f"""
                    SELECT {PRODUCT_COLUMNS}
                    FROM shop_product
                    WHERE id IN ({placeholders})
                    ORDER BY id ASC
                    FOR UPDATE
                    """,
                    product_ids,
                )
                products = await cursor.fetchall()
                if len(products) != len(product_ids):
                    await connection.rollback()
                    return None, "product_not_found"

                total_amount_cents = 0
                order_items = []
                for product in products:
                    product_id = int(product["id"])
                    quantity = int(quantity_by_product[product_id])
                    if int(product["status"]) != 1:
                        await connection.rollback()
                        return None, "product_disabled"
                    if int(product["stock"]) < quantity:
                        await connection.rollback()
                        return None, "insufficient_stock"
                    price_cents = int(product["price_cents"])
                    subtotal = price_cents * quantity
                    total_amount_cents += subtotal
                    order_items.append(
                        {
                            "product_id": product_id,
                            "product_no_snapshot": product["product_no"],
                            "product_name_snapshot": product["product_name"],
                            "image_url_snapshot": product.get("image_url") or "",
                            "price_cents": price_cents,
                            "quantity": quantity,
                            "subtotal_cents": subtotal,
                        }
                    )

                member_account = await member_repository.get_or_create_account_for_update(cursor, user_id)
                balance_before = int(member_account.get("balance_cents") or 0)
                points_before = int(member_account.get("points") or 0)
                if balance_before < total_amount_cents:
                    await connection.rollback()
                    return None, "insufficient_balance"
                balance_after = balance_before - total_amount_cents

                await cursor.execute(
                    """
                    INSERT INTO shop_order
                      (order_no, user_id, status, total_amount_cents, pay_method, paid_at, remark)
                    VALUES (%s, %s, 'paid', %s, 'balance', NOW(), %s)
                    """,
                    (order_no, user_id, total_amount_cents, remark),
                )
                order_id = int(cursor.lastrowid)

                for item in order_items:
                    await cursor.execute(
                        """
                        INSERT INTO shop_order_item
                          (order_id, product_id, product_no_snapshot, product_name_snapshot, image_url_snapshot,
                           price_cents, quantity, subtotal_cents)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            order_id,
                            item["product_id"],
                            item["product_no_snapshot"],
                            item["product_name_snapshot"],
                            item["image_url_snapshot"],
                            item["price_cents"],
                            item["quantity"],
                            item["subtotal_cents"],
                        ),
                    )
                    await cursor.execute(
                        """
                        UPDATE shop_product
                        SET stock = stock - %s,
                            sold_count = sold_count + %s
                        WHERE id = %s
                        """,
                        (item["quantity"], item["quantity"], item["product_id"]),
                    )

                await cursor.execute(
                    "UPDATE member_account SET balance_cents = %s WHERE user_id = %s",
                    (balance_after, user_id),
                )
                await member_repository.insert_member_transaction_with_cursor(
                    cursor,
                    user_id=user_id,
                    reservation_id=None,
                    shop_order_id=order_id,
                    transaction_type="shop_purchase",
                    balance_change_cents=-total_amount_cents,
                    points_change=0,
                    balance_before_cents=balance_before,
                    balance_after_cents=balance_after,
                    points_before=points_before,
                    points_after=points_before,
                    reason=f"商城余额支付 {order_no}",
                    operator_id=user_id,
                    operator_username=user.get("username"),
                )
            await connection.commit()
            return order_id, None
        except Exception:
            await connection.rollback()
            raise
        finally:
            await connection.autocommit(True)


async def list_orders(
    settings: Settings,
    *,
    user_id: int | None,
    status: str | None,
    username: str | None,
    offset: int,
    limit: int,
) -> list[dict[str, Any]]:
    where = []
    args: list[Any] = []
    if user_id is not None:
        where.append("o.user_id = %s")
        args.append(user_id)
    if status:
        where.append("o.status = %s")
        args.append(status)
    if username:
        where.append("(u.username LIKE %s OR u.nickname LIKE %s)")
        args.extend([f"%{username}%", f"%{username}%"])
    where_sql = "WHERE " + " AND ".join(where) if where else ""
    args.extend([offset, limit])
    return await fetch_all(
        settings,
        f"""
        SELECT {ORDER_COLUMNS}
        FROM shop_order o
        JOIN user u ON u.id = o.user_id
        {where_sql}
        ORDER BY o.created_at DESC, o.id DESC
        LIMIT %s, %s
        """,
        args,
    )


async def count_orders(
    settings: Settings,
    *,
    user_id: int | None,
    status: str | None,
    username: str | None,
) -> int:
    where = []
    args: list[Any] = []
    if user_id is not None:
        where.append("o.user_id = %s")
        args.append(user_id)
    if status:
        where.append("o.status = %s")
        args.append(status)
    if username:
        where.append("(u.username LIKE %s OR u.nickname LIKE %s)")
        args.extend([f"%{username}%", f"%{username}%"])
    where_sql = "WHERE " + " AND ".join(where) if where else ""
    row = await fetch_one(
        settings,
        f"""
        SELECT COUNT(*) AS total
        FROM shop_order o
        JOIN user u ON u.id = o.user_id
        {where_sql}
        """,
        args,
    )
    return int(row["total"]) if row else 0


async def get_order(settings: Settings, order_id: int) -> dict[str, Any] | None:
    return await fetch_one(
        settings,
        f"""
        SELECT {ORDER_COLUMNS}
        FROM shop_order o
        JOIN user u ON u.id = o.user_id
        WHERE o.id = %s
        """,
        (order_id,),
    )


async def list_order_items(settings: Settings, order_id: int) -> list[dict[str, Any]]:
    return await fetch_all(
        settings,
        f"""
        SELECT {ORDER_ITEM_COLUMNS}
        FROM shop_order_item
        WHERE order_id = %s
        ORDER BY id ASC
        """,
        (order_id,),
    )


async def request_refund_atomic(
    settings: Settings,
    *,
    order_id: int,
    current_user_id: int,
    reason: str,
) -> tuple[int | None, str | None]:
    pool = await get_pool(settings)
    async with pool.acquire() as connection:
        await connection.autocommit(False)
        try:
            await connection.begin()
            async with connection.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    """
                    SELECT id, user_id, status
                    FROM shop_order
                    WHERE id = %s
                    FOR UPDATE
                    """,
                    (order_id,),
                )
                order = await cursor.fetchone()
                if order is None:
                    await connection.rollback()
                    return None, "not_found"
                if int(order["user_id"]) != current_user_id:
                    await connection.rollback()
                    return None, "not_found"
                if order["status"] == "refund_requested":
                    await connection.rollback()
                    return None, "already_requested"
                if order["status"] != "paid":
                    await connection.rollback()
                    return None, "not_paid"
                await cursor.execute(
                    """
                    UPDATE shop_order
                    SET status = 'refund_requested',
                        refund_requested_at = NOW(),
                        refund_request_reason = %s,
                        refund_reviewed_at = NULL,
                        refund_reject_reason = NULL
                    WHERE id = %s
                    """,
                    (reason, order_id),
                )
            await connection.commit()
            return order_id, None
        except Exception:
            await connection.rollback()
            raise
        finally:
            await connection.autocommit(True)


async def reject_refund_request_atomic(
    settings: Settings,
    *,
    order_id: int,
    reason: str,
) -> tuple[int | None, str | None]:
    pool = await get_pool(settings)
    async with pool.acquire() as connection:
        await connection.autocommit(False)
        try:
            await connection.begin()
            async with connection.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT id, status FROM shop_order WHERE id = %s FOR UPDATE",
                    (order_id,),
                )
                order = await cursor.fetchone()
                if order is None:
                    await connection.rollback()
                    return None, "not_found"
                if order["status"] != "refund_requested":
                    await connection.rollback()
                    return None, "not_refund_requested"
                await cursor.execute(
                    """
                    UPDATE shop_order
                    SET status = 'paid',
                        refund_reviewed_at = NOW(),
                        refund_reject_reason = %s
                    WHERE id = %s
                    """,
                    (reason, order_id),
                )
            await connection.commit()
            return order_id, None
        except Exception:
            await connection.rollback()
            raise
        finally:
            await connection.autocommit(True)


async def cancel_order_atomic(
    settings: Settings,
    *,
    order_id: int,
    current_user_id: int | None,
    operator_id: int | None,
    operator_username: str | None,
    reason: str,
) -> tuple[int | None, str | None]:
    pool = await get_pool(settings)
    async with pool.acquire() as connection:
        await connection.autocommit(False)
        try:
            await connection.begin()
            async with connection.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    """
                    SELECT id, order_no, user_id, status, total_amount_cents
                    FROM shop_order
                    WHERE id = %s
                    FOR UPDATE
                    """,
                    (order_id,),
                )
                order = await cursor.fetchone()
                if order is None:
                    await connection.rollback()
                    return None, "not_found"
                if current_user_id is not None and int(order["user_id"]) != current_user_id:
                    await connection.rollback()
                    return None, "not_found"
                if order["status"] not in {"paid", "refund_requested"}:
                    await connection.rollback()
                    return None, "not_paid"

                await cursor.execute(
                    """
                    SELECT id, product_id, quantity
                    FROM shop_order_item
                    WHERE order_id = %s
                    ORDER BY product_id ASC
                    FOR UPDATE
                    """,
                    (order_id,),
                )
                items = await cursor.fetchall()
                if not items:
                    await connection.rollback()
                    return None, "item_not_found"

                product_ids = [int(item["product_id"]) for item in items]
                placeholders = ",".join(["%s"] * len(product_ids))
                await cursor.execute(
                    f"""
                    SELECT id
                    FROM shop_product
                    WHERE id IN ({placeholders})
                    ORDER BY id ASC
                    FOR UPDATE
                    """,
                    product_ids,
                )
                await cursor.fetchall()
                for item in items:
                    await cursor.execute(
                        """
                        UPDATE shop_product
                        SET stock = stock + %s,
                            sold_count = GREATEST(sold_count - %s, 0)
                        WHERE id = %s
                        """,
                        (item["quantity"], item["quantity"], item["product_id"]),
                    )

                user_id = int(order["user_id"])
                member_account = await member_repository.get_or_create_account_for_update(cursor, user_id)
                balance_before = int(member_account.get("balance_cents") or 0)
                points_before = int(member_account.get("points") or 0)
                refund_cents = int(order.get("total_amount_cents") or 0)
                balance_after = balance_before + refund_cents

                await cursor.execute(
                    """
                    UPDATE shop_order
                    SET status = 'canceled',
                        canceled_at = NOW(),
                        cancel_reason = %s,
                        refund_reviewed_at = CASE
                          WHEN refund_requested_at IS NOT NULL AND refund_reviewed_at IS NULL THEN NOW()
                          ELSE refund_reviewed_at
                        END
                    WHERE id = %s
                    """,
                    (reason, order_id),
                )
                await cursor.execute(
                    "UPDATE member_account SET balance_cents = %s WHERE user_id = %s",
                    (balance_after, user_id),
                )
                await member_repository.insert_member_transaction_with_cursor(
                    cursor,
                    user_id=user_id,
                    reservation_id=None,
                    shop_order_id=order_id,
                    transaction_type="shop_refund",
                    balance_change_cents=refund_cents,
                    points_change=0,
                    balance_before_cents=balance_before,
                    balance_after_cents=balance_after,
                    points_before=points_before,
                    points_after=points_before,
                    reason=reason,
                    operator_id=operator_id,
                    operator_username=operator_username,
                )
            await connection.commit()
            return order_id, None
        except Exception:
            await connection.rollback()
            raise
        finally:
            await connection.autocommit(True)


async def complete_order_atomic(settings: Settings, order_id: int) -> tuple[int | None, str | None]:
    pool = await get_pool(settings)
    async with pool.acquire() as connection:
        await connection.autocommit(False)
        try:
            await connection.begin()
            async with connection.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT id, status FROM shop_order WHERE id = %s FOR UPDATE",
                    (order_id,),
                )
                order = await cursor.fetchone()
                if order is None:
                    await connection.rollback()
                    return None, "not_found"
                if order["status"] != "paid":
                    await connection.rollback()
                    return None, "not_paid"
                await cursor.execute(
                    "UPDATE shop_order SET status = 'completed', completed_at = NOW() WHERE id = %s",
                    (order_id,),
                )
            await connection.commit()
            return order_id, None
        except Exception:
            await connection.rollback()
            raise
        finally:
            await connection.autocommit(True)
