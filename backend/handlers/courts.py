from handlers.base import BaseHandler
from services import court_service
from services.config_service import public_reservation_rules
from utils.query import pagination
from utils.response import ApiError, success


class CourtsHandler(BaseHandler):
    async def get(self) -> None:
        await self.require_current_user()
        settings = self.application.settings["app_settings"]
        page, page_size, offset = pagination(self)
        data = await court_service.list_courts(
            settings,
            status_arg=self.get_argument("status", None),
            page=page,
            page_size=page_size,
            offset=offset,
        )
        self.write_json(success(data))


class VenueInfoHandler(BaseHandler):
    async def get(self) -> None:
        rules = await public_reservation_rules(self.application.settings["app_settings"])
        self.write_json(success({
            "business_start_time": rules["business_start_time"],
            "business_end_time": rules["business_end_time"],
        }))


class CourtRulesHandler(BaseHandler):
    async def get(self) -> None:
        await self.require_current_user()
        data = await public_reservation_rules(self.application.settings["app_settings"])
        self.write_json(success(data))


class CourtSlotsHandler(BaseHandler):
    async def get(self, court_id: str) -> None:
        await self.require_current_user()
        date_arg = self.get_argument("date", None)
        if not date_arg:
            raise ApiError(400, "预约日期不能为空", 400)
        settings = self.application.settings["app_settings"]
        data = await court_service.get_slots(settings, court_id=self.path_int(court_id, "场地ID"), date_arg=date_arg)
        self.write_json(success(data))
