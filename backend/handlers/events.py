from handlers.base import BaseHandler
from services import event_service
from utils.query import pagination
from utils.response import ApiError, success


async def _optional_user(handler: BaseHandler) -> dict | None:
    if not handler.request.headers.get("Authorization", "").startswith("Bearer "):
        return None
    try:
        return await handler.require_current_user()
    except ApiError:
        return None


class EventsHandler(BaseHandler):
    async def get(self) -> None:
        settings = self.application.settings["app_settings"]
        page, page_size, offset = pagination(self)
        current_user = await _optional_user(self)
        data = await event_service.list_public_events(
            settings,
            user_id=current_user["id"] if current_user else None,
            page=page,
            page_size=page_size,
            offset=offset,
        )
        self.write_json(success(data))


class EventDetailHandler(BaseHandler):
    async def get(self, event_id: str) -> None:
        settings = self.application.settings["app_settings"]
        current_user = await _optional_user(self)
        event = await event_service.get_public_event(
            settings,
            self.path_int(event_id, "活动ID"),
            user_id=current_user["id"] if current_user else None,
        )
        self.write_json(success(event))


class EventRegisterHandler(BaseHandler):
    async def post(self, event_id: str) -> None:
        settings = self.application.settings["app_settings"]
        current_user = await self.require_current_user()
        event = await event_service.register_event(
            settings,
            current_user=current_user,
            event_id=self.path_int(event_id, "活动ID"),
        )
        self.write_json(success(event, "报名成功"))


class EventCancelRegistrationHandler(BaseHandler):
    async def put(self, event_id: str) -> None:
        settings = self.application.settings["app_settings"]
        current_user = await self.require_current_user()
        event = await event_service.cancel_registration(
            settings,
            current_user=current_user,
            event_id=self.path_int(event_id, "活动ID"),
        )
        self.write_json(success(event, "报名已取消"))
