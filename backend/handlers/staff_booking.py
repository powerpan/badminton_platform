from handlers.base import BaseHandler
from services import staff_booking_service as service
from utils.response import success


class WalkInQuoteHandler(BaseHandler):
    async def post(self):
        actor = await self.require_frontdesk()
        self.write_json(success(await service.quote(self.application.settings['app_settings'],actor,self.get_json_body())))


class WalkInsHandler(BaseHandler):
    async def get(self):
        await self.require_frontdesk()
        params = {k:self.get_argument(k,None) for k in ('date','page','page_size','court_id','status','order_no')}
        self.write_json(success(await service.list_orders(self.application.settings['app_settings'],params)))

    async def post(self):
        actor = await self.require_frontdesk()
        self.write_json(success(await service.create(self.application.settings['app_settings'],actor,self.get_json_body())))


class WalkInDetailHandler(BaseHandler):
    async def get(self, reservation_id):
        await self.require_frontdesk()
        self.write_json(success(await service.repository.get_order(self.application.settings['app_settings'],self.path_int(reservation_id,'订场ID'))))


class WalkInCancelHandler(BaseHandler):
    async def post(self, reservation_id):
        actor = await self.require_frontdesk()
        self.write_json(success(await service.action(self.application.settings['app_settings'],actor,
            self.path_int(reservation_id,'订场ID'),'cancel',self.get_json_body())))


class WalkInExtensionQuoteHandler(BaseHandler):
    async def post(self, reservation_id):
        actor = await self.require_frontdesk()
        self.write_json(success(await service.quote(self.application.settings['app_settings'],actor,
            self.get_json_body(),self.path_int(reservation_id,'订场ID'))))


class WalkInExtensionsHandler(BaseHandler):
    async def post(self, reservation_id):
        actor = await self.require_frontdesk()
        self.write_json(success(await service.create(self.application.settings['app_settings'],actor,
            self.get_json_body(),self.path_int(reservation_id,'订场ID'))))


class StaffPaymentHandler(BaseHandler):
    async def get(self, payment_id):
        from services import payment_service
        actor=await self.require_current_user()
        settings = self.application.settings['app_settings']
        self.write_json(success(await payment_service.get(settings,actor,self.path_int(payment_id,'支付单ID'))))


class MockPaymentActionHandler(BaseHandler):
    async def post(self, payment_id, action):
        from services import payment_service
        actor=await self.require_current_user()
        settings = self.application.settings['app_settings']
        self.write_json(success(await payment_service.act(settings,actor,self.path_int(payment_id,'支付单ID'),'mock_'+action,self.get_json_body())))


class BalancePaymentHandler(BaseHandler):
    async def post(self, payment_id):
        from services import payment_service
        actor=await self.require_customer()
        self.write_json(success(await payment_service.act(self.application.settings['app_settings'],actor,
            self.path_int(payment_id,'支付单ID'),'balance_pay',self.get_json_body())))


class CancelSupplementHandler(BaseHandler):
    async def post(self, payment_id):
        from services import payment_service
        actor=await self.require_customer()
        self.write_json(success(await payment_service.act(self.application.settings['app_settings'],actor,
            self.path_int(payment_id,'支付单ID'),'cancel',self.get_json_body())))
