from typing import Any

from config.settings import Settings
from repositories import member_repository
from utils.query import clean_text
from utils.response import ApiError


VALID_TRANSACTION_TYPES = {
    "admin_adjust",
    "reservation_charge",
    "reservation_refund",
    "shop_purchase",
    "shop_refund",
}

TRANSACTION_TYPE_LABELS = {
    "admin_adjust": "后台调整",
    "reservation_charge": "预约扣款",
    "reservation_refund": "预约退款",
    "shop_purchase": "商城支付",
    "shop_refund": "商城退款",
}


def _parse_transaction_type(value: Any) -> str | None:
    transaction_type = clean_text(value)
    if not transaction_type or transaction_type == "all":
        return None
    if transaction_type not in VALID_TRANSACTION_TYPES:
        raise ApiError(400, "流水类型参数错误", 400)
    return transaction_type


def _public_transaction(row: dict[str, Any]) -> dict[str, Any]:
    transaction_type = row["transaction_type"]
    return {
        "id": row["id"],
        "transaction_type": transaction_type,
        "transaction_type_label": TRANSACTION_TYPE_LABELS.get(transaction_type, transaction_type),
        "balance_change_cents": int(row.get("balance_change_cents") or 0),
        "points_change": int(row.get("points_change") or 0),
        "balance_before_cents": int(row.get("balance_before_cents") or 0),
        "balance_after_cents": int(row.get("balance_after_cents") or 0),
        "points_before": int(row.get("points_before") or 0),
        "points_after": int(row.get("points_after") or 0),
        "reason": row.get("reason"),
        "reservation_id": row.get("reservation_id"),
        "shop_order_id": row.get("shop_order_id"),
        "operator_username": row.get("operator_username"),
        "created_at": row.get("created_at"),
    }


async def list_my_transactions(
    settings: Settings,
    *,
    current_user: dict[str, Any],
    transaction_type_arg: Any,
    page: int,
    page_size: int,
    offset: int,
) -> dict[str, Any]:
    transaction_type = _parse_transaction_type(transaction_type_arg)
    rows = await member_repository.list_member_transactions(
        settings,
        user_id=current_user["id"],
        transaction_type=transaction_type,
        offset=offset,
        limit=page_size,
    )
    total = await member_repository.count_member_transactions(
        settings,
        user_id=current_user["id"],
        transaction_type=transaction_type,
    )
    return {
        "items": [_public_transaction(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
