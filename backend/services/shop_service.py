import time as time_module
from typing import Any

from config.settings import Settings
from repositories import shop_repository, member_repository
from repositories import shop_checkout_repository as checkout
from repositories.database import fetch_one
from services.config_service import get_reservation_rules
from utils.staff_booking import request_key, text_field, json_value
from uuid import uuid4
from services import notification_service
from utils.query import clean_text
from utils.response import ApiError


DEFAULT_PRODUCT_IMAGE_URL = "/courts/default-court.png"
ORDER_STATUSES = {"pending", "expired", "paid", "refund_requested", "completed", "canceled"}


def pay_method(body):
    method = body.get('pay_method', 'balance')
    if method not in ('balance', 'mock_alipay'):
        raise ApiError(400, '请选择储值余额或模拟支付宝', 400)
    return method


def command_key(body, fallback=None):
    return request_key(body) if 'request_key' in body else fallback or uuid4().hex


def _order_no() -> str:
    return "S" + time_module.strftime("%Y%m%d%H%M%S") + str(time_module.time_ns() % 1_000_000).zfill(6)


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


def _parse_refund_reason(body: dict[str, Any], *, default: str) -> str:
    reason = clean_text(body.get("reason"), default) or default
    if len(reason) > 255:
        raise ApiError(400, "退款原因不能超过255个字符", 400)
    return reason


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
    product['reserved_stock'] = int(product.get('reserved_stock') or 0)
    product['available_stock'] = int(product.get('available_stock', product['stock']))
    product["sold_count"] = int(product.get("sold_count") or 0)
    product["status"] = int(product.get("status") or 0)
    product["image_url"] = clean_text(product.get("image_url"), DEFAULT_PRODUCT_IMAGE_URL) or DEFAULT_PRODUCT_IMAGE_URL
    return product


def _normalize_order(row: dict[str, Any], items: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    order = dict(row)
    order["total_amount_cents"] = int(order.get("total_amount_cents") or 0)
    if items is not None:
        order["items"] = [_normalize_order_item(item) for item in items]
    return json_value(order)


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


def _parse_order_items(value: Any, *, require_prices: bool = False) -> list[dict[str, int]]:
    if not isinstance(value, list) or not value:
        raise ApiError(400, "订单商品不能为空", 400)
    quantity_by_product: dict[int, int] = {}
    prices: dict[int, int] = {}
    for raw_item in value:
        if not isinstance(raw_item, dict):
            raise ApiError(400, "订单商品格式错误", 400)
        if type(raw_item.get('product_id')) is not int or type(raw_item.get('quantity')) is not int:
            raise ApiError(400, '商品ID与数量必须为整数', 400)
        try:
            product_id = int(raw_item.get("product_id"))
            quantity = int(raw_item.get("quantity"))
        except (TypeError, ValueError) as exc:
            raise ApiError(400, "订单商品格式错误", 400) from exc
        if product_id <= 0:
            raise ApiError(400, "商品ID格式错误", 400)
        if quantity < 1 or quantity > 99:
            raise ApiError(400, "单个商品购买数量范围应为 1-99", 400)
        if require_prices:
            expected = raw_item.get('expected_price_cents')
            if type(expected) is not int or expected < 1 or expected > 9999999:
                raise ApiError(400, '请重新核对商品价格后确认支付', 400)
            if product_id in prices and prices[product_id] != expected:
                raise ApiError(400, '同一商品的确认价格不一致', 400)
            prices[product_id] = expected
        quantity_by_product[product_id] = quantity_by_product.get(product_id, 0) + quantity
        if quantity_by_product[product_id] > 99:
            raise ApiError(400, '单个商品购买数量范围应为 1-99', 400)
    if len(quantity_by_product) > 20:
        raise ApiError(400, "单个订单最多包含20种商品", 400)
    return [
        {"product_id": product_id, "quantity": quantity_by_product[product_id], **({"expected_price_cents": prices[product_id]} if require_prices else {})}
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
    await checkout.expire(settings, order_id)
    order = await shop_repository.get_order(settings, order_id)
    if order is None:
        raise ApiError(404, "订单不存在", 404)
    items = await shop_repository.list_order_items(settings, order_id)
    return {**_normalize_order(order, items), **json_value(await fetch_one(settings, 'SELECT NOW() AS server_now'))}


async def quote_order(settings: Settings, *, current_user: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
    method = pay_method(body)
    items = _parse_order_items(body.get('items'))
    products = {row['id']: _normalize_product(row) for row in await shop_repository.get_products_by_ids(settings, [i['product_id'] for i in items])}
    lines, issues = [], []
    for item in items:
        product = products.get(item['product_id'])
        if product is None:
            raise ApiError(404, '购物车中有商品已不存在，请移除后重试', 404)
        if product['status'] != 1:
            issues.append(f"{product['product_name']}已下架，请移除")
        elif product['available_stock'] < item['quantity']:
            issues.append(f"{product['product_name']}库存不足，当前可售 {product['available_stock']} 件")
        lines.append({'product': product, 'quantity': item['quantity'], 'subtotal_cents': product['price_cents'] * item['quantity']})
    balance = await member_repository.get_booking_balance(settings, current_user['id'])
    total = sum(line['subtotal_cents'] for line in lines)
    if method == 'balance' and balance['available_balance_cents'] < total:
            issues.append('会员可用余额不足，请处理待付款订单、充值或选择模拟支付宝')
    if total > 2_147_483_647:
        issues.append('订单金额超出允许范围，请减少商品')
    return {'items': lines, 'total_amount_cents': total, 'pay_method': method, **balance, 'issues': issues, 'can_checkout': not issues}


async def create_order(settings: Settings, *, current_user: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
    items = _parse_order_items(body.get('items'), require_prices=True)
    method = pay_method(body)
    key = command_key(body)
    remark = text_field(body, 'remark', 255)
    rules = await get_reservation_rules(settings)
    await checkout.expire(settings)
    oid = await checkout.create(settings, current_user, items, method, remark, key, rules.reservation_payment_timeout_minutes)
    return await _order_detail(settings, oid)


async def list_my_orders(
    settings: Settings,
    *,
    current_user: dict[str, Any],
    status_arg: Any,
    page: int,
    page_size: int,
    offset: int,
) -> dict[str, Any]:
    await checkout.expire(settings)
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
    return {"items": [_normalize_order(row) for row in rows], "total": total, "page": page, "page_size": page_size, **json_value(await fetch_one(settings, "SELECT NOW() AS server_now"))}


async def get_my_order(settings: Settings, *, current_user: dict[str, Any], order_id: int) -> dict[str, Any]:
    order = await _order_detail(settings, order_id)
    if int(order["user_id"]) != current_user["id"]:
        raise ApiError(404, "订单不存在", 404)
    return order


async def cancel_my_order(settings: Settings, *, current_user: dict[str, Any], order_id: int, body=None) -> dict[str, Any]:
    body = body or {}
    return await checkout.action(settings, current_user, order_id, 'cancel', command_key(body),
                                 _parse_refund_reason(body, default='用户取消商城订单'))


async def request_my_refund(settings: Settings, *, current_user: dict[str, Any], order_id: int, body: dict[str, Any]) -> dict[str, Any]:
    return await checkout.action(settings, current_user, order_id, 'request_refund', command_key(body),
                                 _parse_refund_reason(body, default='用户申请商城订单退款'))


async def list_admin_orders(
    settings: Settings,
    *,
    status_arg: Any,
    username_arg: Any,
    page: int,
    page_size: int,
    offset: int,
) -> dict[str, Any]:
    await checkout.expire(settings)
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
    return {"items": [_normalize_order(row) for row in rows], "total": total, "page": page, "page_size": page_size, **json_value(await fetch_one(settings, "SELECT NOW() AS server_now"))}


async def get_admin_order(settings: Settings, order_id: int) -> dict[str, Any]:
    return await _order_detail(settings, order_id)


async def admin_cancel_order(settings: Settings, *, current_user: dict[str, Any], order_id: int, body=None) -> dict[str, Any]:
    body = body or {}
    return await checkout.action(settings, current_user, order_id, 'refund', command_key(body, f'admin-shop-cancel-{order_id}'),
                                 _parse_refund_reason(body, default='管理员取消商城订单退款'))


async def reject_refund_request(settings: Settings, *, current_user: dict[str, Any], order_id: int, body: dict[str, Any]) -> dict[str, Any]:
    return await checkout.action(settings, current_user, order_id, 'reject', command_key(body),
                                 _parse_refund_reason(body, default='管理员驳回商城订单退款申请'))


async def complete_order(settings: Settings, *, current_user: dict[str, Any], order_id: int, body=None) -> dict[str, Any]:
    body = body or {}
    if current_user.get('role') != 'admin':
        raise ApiError(403, '只有管理员可从订单完成入口核销', 403)
    return await checkout.action(settings, current_user, order_id, 'redeem', command_key(body, f'admin-shop-complete-{order_id}'))
