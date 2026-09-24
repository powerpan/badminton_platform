from handlers.base import BaseHandler
from services import recharge_service as service
from utils.response import success


class RechargeCustomersHandler(BaseHandler):
    async def get(self):
        actor = await self.require_frontdesk()
        self.set_header('Cache-Control', 'no-store')
        self.write_json(success(await service.find_customers(self.application.settings['app_settings'], actor, self.get_argument('query', ''))))


class RechargesHandler(BaseHandler):
    async def get(self):
        actor = await self.require_frontdesk()
        self.set_header('Cache-Control', 'no-store')
        params = {k: self.get_argument(k, None) for k in ('date_from', 'date_to', 'status', 'order_no', 'page', 'page_size')}
        self.write_json(success(await service.list_orders(self.application.settings['app_settings'], actor, params)))

    async def post(self):
        actor = await self.require_frontdesk()
        self.write_json(success(await service.create(self.application.settings['app_settings'], actor, self.get_json_body())))


class RechargeDetailHandler(BaseHandler):
    async def get(self, oid):
        actor = await self.require_frontdesk()
        self.set_header('Cache-Control', 'no-store')
        self.write_json(success(await service.repository.get(self.application.settings['app_settings'], actor, self.path_int(oid, '充值单ID'))))


class RechargeCancelHandler(BaseHandler):
    async def post(self, oid):
        actor = await self.require_frontdesk()
        self.write_json(success(await service.cancel(self.application.settings['app_settings'], actor, self.path_int(oid, '充值单ID'), self.get_json_body())))


class AdminRechargesHandler(BaseHandler):
    async def get(self):
        actor = await self.require_admin()
        self.set_header('Cache-Control', 'no-store')
        params = {k: self.get_argument(k, None) for k in ('date_from', 'date_to', 'status', 'order_no', 'page', 'page_size')}
        self.write_json(success(await service.list_orders(self.application.settings['app_settings'], actor, params)))


class AdminRechargeDetailHandler(BaseHandler):
    async def get(self, oid):
        actor = await self.require_admin()
        self.set_header('Cache-Control', 'no-store')
        self.write_json(success(await service.repository.get(self.application.settings['app_settings'], actor, self.path_int(oid, '充值单ID'))))
