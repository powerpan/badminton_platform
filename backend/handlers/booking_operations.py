from datetime import date, timedelta
from handlers.base import BaseHandler
from services import booking_operations_service as service, operations_statistics_service
from services.reservation_service import get_admin_reservation
from repositories import booking_operations_repository as repository
from utils.response import success


class RecommendationsHandler(BaseHandler):
    async def post(self):
        actor = await self.require_current_user()
        self.write_json(success(await service.recommendations(self.application.settings['app_settings'], self.get_json_body(), actor)))


class RescheduleQuoteHandler(BaseHandler):
    async def post(self, reservation_id):
        actor = await self.require_current_user()
        self.write_json(success(await service.quote(self.application.settings['app_settings'], self.path_int(reservation_id,'预约ID'), self.get_json_body(), actor)))


class RescheduleHandler(BaseHandler):
    async def put(self, reservation_id):
        actor = await self.require_current_user()
        self.write_json(success(await service.reschedule(self.application.settings['app_settings'], self.path_int(reservation_id,'预约ID'), self.get_json_body(), actor)))


class ReservationChangesHandler(BaseHandler):
    async def get(self, reservation_id):
        actor = await self.require_current_user()
        settings = self.application.settings['app_settings']
        rid = self.path_int(reservation_id,'预约ID')
        if actor['role'] == 'admin': await get_admin_reservation(settings,rid)
        else: await service.detail(settings,rid,actor)
        self.write_json(success({'items': await repository.change_history(settings,rid)}))


class CourtBlocksHandler(BaseHandler):
    async def get(self):
        await self.require_admin()
        self.write_json(success(await service.blocks(self.application.settings['app_settings'],
            self.get_argument('date_from',str(date.today())), self.get_argument('date_to',str(date.today()+timedelta(days=30))))))

    async def post(self):
        actor = await self.require_admin()
        self.write_json(success(await service.create_block(self.application.settings['app_settings'],self.get_json_body(),actor)))


class ReleaseCourtBlockHandler(BaseHandler):
    async def put(self, block_id):
        actor = await self.require_admin()
        await repository.release_block(self.application.settings['app_settings'],self.path_int(block_id,'维护ID'),actor)
        self.write_json(success())


class AttendanceHandler(BaseHandler):
    async def put(self, reservation_id):
        actor = await self.require_admin()
        settings = self.application.settings['app_settings']
        rid = self.path_int(reservation_id,'预约ID')
        await repository.record_attendance(settings,rid,self.get_json_body().get('outcome'),actor)
        self.write_json(success(await get_admin_reservation(settings,rid)))


class OperationsStatisticsHandler(BaseHandler):
    async def get(self):
        await self.require_admin()
        self.write_json(success(await operations_statistics_service.report(self.application.settings['app_settings'],
            self.get_argument('date_from',str(date.today()-timedelta(days=6))), self.get_argument('date_to',str(date.today())))))
