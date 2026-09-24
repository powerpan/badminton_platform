"""Stock holds are serialized by the corresponding shop_product row lock."""

RESERVED_SQL = "COALESCE((SELECT SUM(h.quantity) FROM shop_stock_hold h WHERE h.product_id=shop_product.id AND h.status='active' AND h.expires_at>NOW()),0)"


async def held_quantity(cursor, product_id, exclude_order=0):
    await cursor.execute("SELECT quantity FROM shop_stock_hold WHERE product_id=%s AND shop_order_id<>%s AND status='active' AND expires_at>NOW() FOR UPDATE",
                         (product_id, exclude_order))
    return sum(int(row['quantity']) for row in await cursor.fetchall())


async def lock_products(cursor, ids):
    result = {}
    for pid in sorted(set(ids)):
        await cursor.execute('SELECT * FROM shop_product WHERE id=%s FOR UPDATE', (pid,))
        row = await cursor.fetchone()
        if row:
            result[pid] = row
    return result
