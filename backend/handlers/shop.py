from handlers.base import BaseHandler
from services import shop_service
from utils.query import pagination
from utils.response import success


class ShopProductsHandler(BaseHandler):
    async def get(self) -> None:
        settings = self.application.settings["app_settings"]
        page, page_size, offset = pagination(self)
        data = await shop_service.list_products(
            settings,
            status_arg=None,
            keyword_arg=self.get_argument("keyword", None),
            page=page,
            page_size=page_size,
            offset=offset,
            public_only=True,
        )
        self.write_json(success(data))


class ShopProductDetailHandler(BaseHandler):
    async def get(self, product_id: str) -> None:
        settings = self.application.settings["app_settings"]
        product = await shop_service.get_public_product(settings, self.path_int(product_id, "商品ID"))
        self.write_json(success(product))


class ShopOrderQuoteHandler(BaseHandler):
    async def post(self) -> None:
        user = await self.require_customer()
        data = await shop_service.quote_order(self.application.settings['app_settings'], current_user=user, body=self.get_json_body())
        self.write_json(success(data))


class ShopOrdersHandler(BaseHandler):
    async def post(self) -> None:
        settings = self.application.settings["app_settings"]
        current_user = await self.require_customer()
        order = await shop_service.create_order(settings, current_user=current_user, body=self.get_json_body())
        self.write_json(success(order, "订单已创建，请完成付款"))


class MyShopOrdersHandler(BaseHandler):
    async def get(self) -> None:
        settings = self.application.settings["app_settings"]
        current_user = await self.require_customer()
        page, page_size, offset = pagination(self)
        data = await shop_service.list_my_orders(
            settings,
            current_user=current_user,
            status_arg=self.get_argument("status", None),
            page=page,
            page_size=page_size,
            offset=offset,
        )
        self.write_json(success(data))


class ShopOrderDetailHandler(BaseHandler):
    async def get(self, order_id: str) -> None:
        settings = self.application.settings["app_settings"]
        current_user = await self.require_customer()
        order = await shop_service.get_my_order(settings, current_user=current_user, order_id=self.path_int(order_id, "订单ID"))
        self.write_json(success(order))


class ShopOrderRefundRequestHandler(BaseHandler):
    async def put(self, order_id: str) -> None:
        settings = self.application.settings["app_settings"]
        current_user = await self.require_customer()
        order = await shop_service.request_my_refund(
            settings,
            current_user=current_user,
            order_id=self.path_int(order_id, "订单ID"),
            body=self.get_json_body(),
        )
        self.write_json(success(order, "退款申请已提交，等待管理员审核"))


class ShopOrderCancelHandler(BaseHandler):
    async def put(self, order_id: str) -> None:
        settings = self.application.settings["app_settings"]
        current_user = await self.require_customer()
        order = await shop_service.cancel_my_order(
            settings,
            current_user=current_user,
            order_id=self.path_int(order_id, "订单ID"),
            body=self.get_json_body(),
        )
        self.write_json(success(order, "订单状态已更新"))
