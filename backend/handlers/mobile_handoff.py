from handlers.base import BaseHandler
from services import mobile_handoff_service as service
from utils.response import success


class HandoffBase(BaseHandler):
    def set_default_headers(self):
        super().set_default_headers()
        self.set_header('Cache-Control', 'no-store')
        self.set_header('Referrer-Policy', 'no-referrer')

    @property
    def config(self):
        return self.application.settings['app_settings']

    @property
    def token(self):
        return self.request.headers.get('Authorization', '').removeprefix('Bearer ').strip()


class MobileHandoffCreateHandler(HandoffBase):
    async def post(self):
        actor = await self.require_roles({'user'})
        self.write_json(success(await service.create(self.config, actor, self.token, self.get_json_body())))


class MobileHandoffStatusHandler(HandoffBase):
    async def get(self, request_id):
        actor = await self.require_roles({'user'})
        self.write_json(success(await service.status(self.config, actor, self.token, request_id)))


class MobileHandoffDecisionHandler(HandoffBase):
    async def post(self, request_id):
        actor = await self.require_roles({'user'})
        self.write_json(success(await service.decide(self.config, actor, self.token, request_id, self.get_json_body())))


class MobileHandoffClaimHandler(HandoffBase):
    async def post(self, request_id):
        await service.limit(self.config, 'claim:' + service.digest(self.request.remote_ip), 60)
        self.write_json(success(await service.claim(self.config, request_id, self.get_json_body())))


class MobileHandoffExchangeHandler(HandoffBase):
    async def post(self, request_id):
        await service.limit(self.config, 'exchange:' + service.digest(self.request.remote_ip), 120)
        self.write_json(success(await service.exchange(self.config, request_id, self.get_json_body())))
