"""The business order is the single source of pending balance reservations."""

HELD_SQL = '''SELECT
    COALESCE((SELECT SUM(amount_cents) FROM reservation_order
        WHERE user_id=%s AND status='pending' AND pay_method='balance' AND expires_at>NOW() AND id<>%s),0)
    + COALESCE((SELECT SUM(total_amount_cents) FROM shop_order
        WHERE user_id=%s AND status='pending' AND pay_method='balance' AND expires_at>NOW() AND id<>%s),0) AS held'''


async def held_balance(cursor, user_id, *, reservation_order_id=0, shop_order_id=0):
    # Writers hold the customer row, so orders cannot be added/paid concurrently.
    await cursor.execute(HELD_SQL,(user_id,reservation_order_id,user_id,shop_order_id))
    return int((await cursor.fetchone())['held'])
