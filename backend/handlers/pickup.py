from handlers.base import BaseHandler
from services import pickup_service
from utils.response import success


class ShopPickupCodeHandler(BaseHandler):
    async def get(self, order_id):
        actor = await self.require_customer()
        self.set_header('Cache-Control', 'no-store')
        self.write_json(success(await pickup_service.get_code(self.application.settings['app_settings'], actor,
                                                              self.path_int(order_id, '订单ID'))))


class PickupLookupHandler(BaseHandler):
    async def post(self):
        actor = await self.require_frontdesk()
        self.set_header('Cache-Control', 'no-store')
        self.write_json(success(await pickup_service.lookup(self.application.settings['app_settings'], actor, self.get_json_body())))


class PickupRedeemHandler(BaseHandler):
    async def post(self):
        actor = await self.require_frontdesk()
        self.write_json(success(await pickup_service.redeem(self.application.settings['app_settings'], actor, self.get_json_body())))
