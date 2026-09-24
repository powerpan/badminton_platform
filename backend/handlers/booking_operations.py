from datetime import date, timedelta
from handlers.base import BaseHandler
from services import booking_operations_service as service, operations_statistics_service
from services.reservation_service import get_admin_reservation
from repositories import booking_operations_repository as repository
from utils.response import success


class RecommendationsHandler(BaseHandler):
    async def post(self):
        actor = await self.require_customer()
        self.write_json(success(await service.recommendations(self.application.settings['app_settings'], self.get_json_body(), actor)))


class RescheduleQuoteHandler(BaseHandler):
    async def post(self, reservation_id):
        actor = await self.require_customer()
        self.write_json(success(await service.quote(self.application.settings['app_settings'], self.path_int(reservation_id,'预约ID'), self.get_json_body(), actor)))


class RescheduleHandler(BaseHandler):
    async def put(self, reservation_id):
        actor = await self.require_customer()
        self.write_json(success(await service.reschedule(self.application.settings['app_settings'], self.path_int(reservation_id,'预约ID'), self.get_json_body(), actor)))


class ReservationChangesHandler(BaseHandler):
    async def get(self, reservation_id):
        actor = await self.require_customer()
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


class ClassifyCourtBlockHandler(BaseHandler):
    async def put(self, block_id):
        actor = await self.require_admin()
        block_type = service.parse_block_type(self.get_json_body().get('block_type'))
        await repository.classify_block(self.application.settings['app_settings'], self.path_int(block_id, '维护ID'), block_type, actor)
        self.write_json(success())


class MaintenanceCourtBlocksHandler(BaseHandler):
    async def get(self):
        await self.require_maintenance()
        court_id = self.get_argument('court_id', None)
        self.write_json(success(await service.maintenance_blocks(
            self.application.settings['app_settings'],
            self.get_argument('date_from', str(date.today())),
            self.get_argument('date_to', str(date.today() + timedelta(days=7))),
            self.path_int(court_id, '场地ID') if court_id else None,
            self.get_argument('status', None))))


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


class FrontdeskCourtSlotsHandler(BaseHandler):
    async def get(self):
        from services import court_service
        from services.config_service import public_reservation_rules
        from repositories import court_repository
        from services.reservation_service import refresh_reservation_statuses
        await self.require_frontdesk()
        settings = self.application.settings['app_settings']
        day = self.get_argument('date', str(date.today()))
        court_service._parse_date(day)
        await refresh_reservation_statuses(settings)
        courts = await court_repository.list_courts(settings, status=None, offset=0, limit=1000)
        items = [await court_service.get_slots(settings, court_id=c['id'], date_arg=day,
                 refresh=False, allow_current=True) for c in courts]
        rules = await public_reservation_rules(settings)
        self.write_json(success({'items': items, 'rules': rules, 'server_now': rules['server_now']}))
