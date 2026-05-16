import time as time_module
from typing import Any

from config.settings import Settings
from repositories import shop_repository
from services import notification_service
from utils.query import clean_text
from utils.response import ApiError


DEFAULT_PRODUCT_IMAGE_URL = "/courts/default-court.png"
ORDER_STATUSES = {"paid", "completed", "canceled"}


def _order_no() -> str:
    return "S" + time_module.strftime("%Y%m%d%H%M%S") + str(int(time_module.time() * 1000) % 1000).zfill(3)


def _parse_status(value: Any, default: int | None = None) -> int | None:
    if value is None or value == "":
        return default
    try:
        status = int(value)
    except (TypeError, ValueError) as exc:
        raise ApiError(400, "状态参数格式错误", 400) from exc
    if status not in (0, 1):
        raise ApiError(400, "状态只能是0或1", 400)
    return status


def _parse_order_status(value: Any) -> str | None:
    status = clean_text(value)
    if not status:
        return None
    if status not in ORDER_STATUSES:
        raise ApiError(400, "订单状态参数不合法", 400)
    return status


def _parse_positive_int(value: Any, field_name: str, default: int, *, min_value: int, max_value: int) -> int:
    if value is None or value == "":
        number = default
    else:
        try:
            number = int(value)
        except (TypeError, ValueError) as exc:
            raise ApiError(400, f"{field_name}格式错误", 400) from exc
    if number < min_value or number > max_value:
        raise ApiError(400, f"{field_name}范围应为 {min_value}-{max_value}", 400)
    return number


def _parse_image_url(value: Any, default: str = DEFAULT_PRODUCT_IMAGE_URL) -> str:
    image_url = clean_text(value, default)
    if not image_url:
        return default
    if image_url.startswith(("http://", "https://", "/")):
        return image_url
    raise ApiError(400, "商品图片地址必须以 http://、https:// 或 / 开头", 400)


def _normalize_product(row: dict[str, Any]) -> dict[str, Any]:
    product = dict(row)
    product["price_cents"] = int(product.get("price_cents") or 0)
    product["stock"] = int(product.get("stock") or 0)
    product["sold_count"] = int(product.get("sold_count") or 0)
    product["status"] = int(product.get("status") or 0)
    product["image_url"] = clean_text(product.get("image_url"), DEFAULT_PRODUCT_IMAGE_URL) or DEFAULT_PRODUCT_IMAGE_URL
    return product


def _normalize_order(row: dict[str, Any], items: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    order = dict(row)
    order["total_amount_cents"] = int(order.get("total_amount_cents") or 0)
    if items is not None:
        order["items"] = [_normalize_order_item(item) for item in items]
    return order


def _normalize_order_item(row: dict[str, Any]) -> dict[str, Any]:
    item = dict(row)
    item["price_cents"] = int(item.get("price_cents") or 0)
    item["quantity"] = int(item.get("quantity") or 0)
    item["subtotal_cents"] = int(item.get("subtotal_cents") or 0)
    item["image_url_snapshot"] = clean_text(item.get("image_url_snapshot"), DEFAULT_PRODUCT_IMAGE_URL) or DEFAULT_PRODUCT_IMAGE_URL
    return item


def _product_payload(body: dict[str, Any], *, existing: dict[str, Any] | None = None) -> dict[str, Any]:
    product_no = clean_text(body.get("product_no", existing.get("product_no") if existing else ""))
    product_name = clean_text(body.get("product_name", existing.get("product_name") if existing else ""))
    description = clean_text(body.get("description", existing.get("description") if existing else ""))
    image_url = _parse_image_url(body.get("image_url", existing.get("image_url") if existing else DEFAULT_PRODUCT_IMAGE_URL))
    price_cents = _parse_positive_int(
        body.get("price_cents", existing.get("price_cents") if existing else 1000),
        "商品价格",
        int(existing.get("price_cents") or 1000) if existing else 1000,
        min_value=1,
        max_value=9999999,
    )
    stock = _parse_positive_int(
        body.get("stock", existing.get("stock") if existing else 0),
        "商品库存",
        int(existing.get("stock") or 0) if existing else 0,
        min_value=0,
        max_value=999999,
    )
    status = _parse_status(body.get("status"), default=int(existing["status"]) if existing else 1)
    if not product_no:
        raise ApiError(400, "商品编号不能为空", 400)
    if len(product_no) > 50:
        raise ApiError(400, "商品编号不能超过50个字符", 400)
    if not product_name:
        raise ApiError(400, "商品名称不能为空", 400)
    if len(product_name) > 100:
        raise ApiError(400, "商品名称不能超过100个字符", 400)
    if len(description) > 1000:
        raise ApiError(400, "商品说明不能超过1000个字符", 400)
    return {
        "product_no": product_no,
        "product_name": product_name,
        "description": description,
        "image_url": image_url,
        "price_cents": price_cents,
        "stock": stock,
        "status": status if status is not None else 1,
    }


def _parse_order_items(value: Any) -> list[dict[str, int]]:
    if not isinstance(value, list) or not value:
        raise ApiError(400, "订单商品不能为空", 400)
    quantity_by_product: dict[int, int] = {}
    for raw_item in value:
        if not isinstance(raw_item, dict):
            raise ApiError(400, "订单商品格式错误", 400)
        try:
            product_id = int(raw_item.get("product_id"))
            quantity = int(raw_item.get("quantity"))
        except (TypeError, ValueError) as exc:
            raise ApiError(400, "订单商品格式错误", 400) from exc
        if product_id <= 0:
            raise ApiError(400, "商品ID格式错误", 400)
        if quantity < 1 or quantity > 99:
            raise ApiError(400, "单个商品购买数量范围应为 1-99", 400)
        quantity_by_product[product_id] = quantity_by_product.get(product_id, 0) + quantity
    if len(quantity_by_product) > 20:
        raise ApiError(400, "单个订单最多包含20种商品", 400)
    return [
        {"product_id": product_id, "quantity": quantity_by_product[product_id]}
        for product_id in sorted(quantity_by_product)
    ]


async def list_products(
    settings: Settings,
    *,
    status_arg: Any,
    keyword_arg: Any,
    page: int,
    page_size: int,
    offset: int,
    public_only: bool,
) -> dict[str, Any]:
    status = 1 if public_only else _parse_status(status_arg, default=None)
    keyword = clean_text(keyword_arg) or None
    rows = await shop_repository.list_products(settings, status=status, keyword=keyword, offset=offset, limit=page_size)
    total = await shop_repository.count_products(settings, status=status, keyword=keyword)
    return {"items": [_normalize_product(row) for row in rows], "total": total, "page": page, "page_size": page_size}


async def get_public_product(settings: Settings, product_id: int) -> dict[str, Any]:
    product = await shop_repository.get_product(settings, product_id)
    if product is None or int(product["status"]) != 1:
        raise ApiError(404, "商品不存在", 404)
    return _normalize_product(product)


async def create_product(settings: Settings, body: dict[str, Any]) -> dict[str, Any]:
    payload = _product_payload(body)
    if await shop_repository.get_product_by_no(settings, payload["product_no"]):
        raise ApiError(409, "商品编号已存在", 409)
    product_id = await shop_repository.create_product(settings, **payload)
    product = await shop_repository.get_product(settings, product_id)
    if product is None:
        raise ApiError(500, "创建商品后读取失败", 500)
    return _normalize_product(product)


async def update_product(settings: Settings, product_id: int, body: dict[str, Any]) -> dict[str, Any]:
    existing = await shop_repository.get_product(settings, product_id)
    if existing is None:
        raise ApiError(404, "商品不存在", 404)
    payload = _product_payload(body, existing=existing)
    duplicate = await shop_repository.get_product_by_no(settings, payload["product_no"])
    if duplicate and int(duplicate["id"]) != product_id:
        raise ApiError(409, "商品编号已存在", 409)
    await shop_repository.update_product(settings, product_id=product_id, **payload)
    updated = await shop_repository.get_product(settings, product_id)
    if updated is None:
        raise ApiError(404, "商品不存在", 404)
    return _normalize_product(updated)


async def update_product_status(settings: Settings, product_id: int, body: dict[str, Any]) -> dict[str, Any]:
    product = await shop_repository.get_product(settings, product_id)
    if product is None:
        raise ApiError(404, "商品不存在", 404)
    status = _parse_status(body.get("status"), default=None)
    if status is None:
        raise ApiError(400, "状态不能为空", 400)
    await shop_repository.update_product_status(settings, product_id, status)
    updated = await shop_repository.get_product(settings, product_id)
    if updated is None:
        raise ApiError(404, "商品不存在", 404)
    return _normalize_product(updated)


async def _order_detail(settings: Settings, order_id: int) -> dict[str, Any]:
    order = await shop_repository.get_order(settings, order_id)
    if order is None:
        raise ApiError(404, "订单不存在", 404)
    items = await shop_repository.list_order_items(settings, order_id)
    return _normalize_order(order, items)


async def create_order(
    settings: Settings,
    *,
    current_user: dict[str, Any],
    body: dict[str, Any],
) -> dict[str, Any]:
    items = _parse_order_items(body.get("items"))
    remark = clean_text(body.get("remark"))
    if len(remark) > 255:
        raise ApiError(400, "订单备注不能超过255个字符", 400)
    order_id, failure = await shop_repository.create_paid_order_atomic(
        settings,
        order_no=_order_no(),
        user_id=current_user["id"],
        items=items,
        remark=remark,
    )
    if failure == "product_not_found":
        raise ApiError(404, "商品不存在", 404)
    if failure == "product_disabled":
        raise ApiError(400, "商品已下架，不能下单", 400)
    if failure == "insufficient_stock":
        raise ApiError(400, "商品库存不足，请调整购买数量", 400)
    if failure == "insufficient_balance":
        raise ApiError(400, "会员余额不足，请联系管理员充值或调整余额", 400)
    if failure == "user_not_found":
        raise ApiError(401, "登录用户不存在，请重新登录", 401)
    if failure == "user_disabled":
        raise ApiError(403, "账号已被禁用", 403)
    if order_id is None:
        raise ApiError(500, "订单创建失败，请重试", 500)
    order = await _order_detail(settings, order_id)
    await notification_service.notify_shop_order_paid(settings, order=order)
    return order


async def list_my_orders(
    settings: Settings,
    *,
    current_user: dict[str, Any],
    status_arg: Any,
    page: int,
    page_size: int,
    offset: int,
) -> dict[str, Any]:
    status = _parse_order_status(status_arg)
    rows = await shop_repository.list_orders(
        settings,
        user_id=current_user["id"],
        status=status,
        username=None,
        offset=offset,
        limit=page_size,
    )
    total = await shop_repository.count_orders(settings, user_id=current_user["id"], status=status, username=None)
    return {"items": [_normalize_order(row) for row in rows], "total": total, "page": page, "page_size": page_size}


async def get_my_order(settings: Settings, *, current_user: dict[str, Any], order_id: int) -> dict[str, Any]:
    order = await _order_detail(settings, order_id)
    if int(order["user_id"]) != current_user["id"]:
        raise ApiError(404, "订单不存在", 404)
    return order


async def cancel_my_order(settings: Settings, *, current_user: dict[str, Any], order_id: int) -> dict[str, Any]:
    canceled_id, failure = await shop_repository.cancel_order_atomic(
        settings,
        order_id=order_id,
        current_user_id=current_user["id"],
        operator_id=current_user["id"],
        operator_username=current_user.get("username"),
        reason="用户取消商城订单退款",
    )
    if failure == "not_found":
        raise ApiError(404, "订单不存在", 404)
    if failure == "not_paid":
        raise ApiError(400, "当前订单状态不能取消退款", 400)
    if canceled_id is None:
        raise ApiError(500, "取消订单失败，请重试", 500)
    order = await _order_detail(settings, canceled_id)
    await notification_service.notify_shop_order_canceled(
        settings,
        order=order,
        by_admin=False,
        operator_id=current_user["id"],
    )
    return order


async def list_admin_orders(
    settings: Settings,
    *,
    status_arg: Any,
    username_arg: Any,
    page: int,
    page_size: int,
    offset: int,
) -> dict[str, Any]:
    status = _parse_order_status(status_arg)
    username = clean_text(username_arg) or None
    rows = await shop_repository.list_orders(
        settings,
        user_id=None,
        status=status,
        username=username,
        offset=offset,
        limit=page_size,
    )
    total = await shop_repository.count_orders(settings, user_id=None, status=status, username=username)
    return {"items": [_normalize_order(row) for row in rows], "total": total, "page": page, "page_size": page_size}


async def get_admin_order(settings: Settings, order_id: int) -> dict[str, Any]:
    return await _order_detail(settings, order_id)


async def admin_cancel_order(
    settings: Settings,
    *,
    current_user: dict[str, Any],
    order_id: int,
) -> dict[str, Any]:
    canceled_id, failure = await shop_repository.cancel_order_atomic(
        settings,
        order_id=order_id,
        current_user_id=None,
        operator_id=current_user["id"],
        operator_username=current_user.get("username"),
        reason="管理员取消商城订单退款",
    )
    if failure == "not_found":
        raise ApiError(404, "订单不存在", 404)
    if failure == "not_paid":
        raise ApiError(400, "当前订单状态不能取消退款", 400)
    if canceled_id is None:
        raise ApiError(500, "取消订单失败，请重试", 500)
    order = await _order_detail(settings, canceled_id)
    await notification_service.notify_shop_order_canceled(
        settings,
        order=order,
        by_admin=True,
        operator_id=current_user["id"],
    )
    return order


async def complete_order(
    settings: Settings,
    *,
    current_user: dict[str, Any],
    order_id: int,
) -> dict[str, Any]:
    completed_id, failure = await shop_repository.complete_order_atomic(settings, order_id)
    if failure == "not_found":
        raise ApiError(404, "订单不存在", 404)
    if failure == "not_paid":
        raise ApiError(400, "只有已支付待处理订单可以完成", 400)
    if completed_id is None:
        raise ApiError(500, "完成订单失败，请重试", 500)
    order = await _order_detail(settings, completed_id)
    await notification_service.notify_shop_order_completed(
        settings,
        order=order,
        operator_id=current_user["id"],
    )
    return order
