from handlers.base import BaseHandler
from services import notification_service
from utils.query import pagination
from utils.response import success


class NotificationsHandler(BaseHandler):
    async def get(self) -> None:
        settings = self.application.settings["app_settings"]
        current_user = await self.require_current_user()
        page, page_size, offset = pagination(self)
        data = await notification_service.list_my_notifications(
            settings,
            current_user=current_user,
            is_read_arg=self.get_argument("is_read", None),
            page=page,
            page_size=page_size,
            offset=offset,
        )
        self.write_json(success(data))


class NotificationUnreadCountHandler(BaseHandler):
    async def get(self) -> None:
        settings = self.application.settings["app_settings"]
        current_user = await self.require_current_user()
        data = await notification_service.get_unread_count(settings, current_user=current_user)
        self.write_json(success(data))


class NotificationReadHandler(BaseHandler):
    async def put(self, notification_id: str) -> None:
        settings = self.application.settings["app_settings"]
        current_user = await self.require_current_user()
        data = await notification_service.mark_notification_read(
            settings,
            current_user=current_user,
            notification_id=self.path_int(notification_id, "通知ID"),
        )
        self.write_json(success(data))


class NotificationReadAllHandler(BaseHandler):
    async def put(self) -> None:
        settings = self.application.settings["app_settings"]
        current_user = await self.require_current_user()
        data = await notification_service.mark_all_read(settings, current_user=current_user)
        self.write_json(success(data))
