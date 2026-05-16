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
        product = await shop_service.get_public_product(settings, int(product_id))
        self.write_json(success(product))


class ShopOrdersHandler(BaseHandler):
    async def post(self) -> None:
        settings = self.application.settings["app_settings"]
        current_user = await self.require_current_user()
        order = await shop_service.create_order(settings, current_user=current_user, body=self.get_json_body())
        self.write_json(success(order, "订单已支付"))


class MyShopOrdersHandler(BaseHandler):
    async def get(self) -> None:
        settings = self.application.settings["app_settings"]
        current_user = await self.require_current_user()
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
        current_user = await self.require_current_user()
        order = await shop_service.get_my_order(settings, current_user=current_user, order_id=int(order_id))
        self.write_json(success(order))


class ShopOrderCancelHandler(BaseHandler):
    async def put(self, order_id: str) -> None:
        settings = self.application.settings["app_settings"]
        current_user = await self.require_current_user()
        order = await shop_service.cancel_my_order(settings, current_user=current_user, order_id=int(order_id))
        self.write_json(success(order, "订单已取消并退款"))
