from handlers.base import BaseHandler
from services import announcement_service
from utils.query import pagination
from utils.response import success


class AnnouncementsHandler(BaseHandler):
    async def get(self) -> None:
        settings = self.application.settings["app_settings"]
        page, page_size, offset = pagination(self)
        data = await announcement_service.list_public_announcements(
            settings,
            page=page,
            page_size=page_size,
            offset=offset,
        )
        self.write_json(success(data))


class AnnouncementDetailHandler(BaseHandler):
    async def get(self, announcement_id: str) -> None:
        settings = self.application.settings["app_settings"]
        data = await announcement_service.get_public_announcement(settings, int(announcement_id))
        self.write_json(success(data))
