from handlers.base import BaseHandler
from services import (
    admin_user_service,
    announcement_service,
    config_service,
    court_service,
    reservation_service,
)
from utils.query import pagination
from utils.response import success


class AdminUsersHandler(BaseHandler):
    async def get(self) -> None:
        await self.require_admin()
        settings = self.application.settings["app_settings"]
        page, page_size, offset = pagination(self)
        data = await admin_user_service.list_users(
            settings,
            role_arg=self.get_argument("role", None),
            status_arg=self.get_argument("status", None),
            page=page,
            page_size=page_size,
            offset=offset,
        )
        self.write_json(success(data))

    async def post(self) -> None:
        await self.require_admin()
        settings = self.application.settings["app_settings"]
        user = await admin_user_service.create_user(settings, self.get_json_body())
        self.write_json(success(user))


class AdminUserStatusHandler(BaseHandler):
    async def put(self, user_id: str) -> None:
        current_user = await self.require_admin()
        settings = self.application.settings["app_settings"]
        user = await admin_user_service.update_user_status(
            settings,
            current_user=current_user,
            user_id=int(user_id),
            body=self.get_json_body(),
        )
        self.write_json(success(user))


class AdminUserRoleHandler(BaseHandler):
    async def put(self, user_id: str) -> None:
        current_user = await self.require_admin()
        settings = self.application.settings["app_settings"]
        user = await admin_user_service.update_user_role(
            settings,
            current_user=current_user,
            user_id=int(user_id),
            body=self.get_json_body(),
        )
        self.write_json(success(user))


class AdminCourtsHandler(BaseHandler):
    async def get(self) -> None:
        await self.require_admin()
        settings = self.application.settings["app_settings"]
        page, page_size, offset = pagination(self)
        data = await court_service.list_admin_courts(
            settings,
            status_arg=self.get_argument("status", None),
            page=page,
            page_size=page_size,
            offset=offset,
        )
        self.write_json(success(data))

    async def post(self) -> None:
        await self.require_admin()
        settings = self.application.settings["app_settings"]
        court = await court_service.create_court(settings, self.get_json_body())
        self.write_json(success(court))


class AdminCourtDetailHandler(BaseHandler):
    async def put(self, court_id: str) -> None:
        await self.require_admin()
        settings = self.application.settings["app_settings"]
        court = await court_service.update_court(settings, int(court_id), self.get_json_body())
        self.write_json(success(court))


class AdminCourtStatusHandler(BaseHandler):
    async def put(self, court_id: str) -> None:
        await self.require_admin()
        settings = self.application.settings["app_settings"]
        court = await court_service.update_court_status(settings, int(court_id), self.get_json_body())
        self.write_json(success(court))


class AdminReservationsHandler(BaseHandler):
    async def get(self) -> None:
        await self.require_admin()
        settings = self.application.settings["app_settings"]
        page, page_size, offset = pagination(self)
        data = await reservation_service.list_admin_reservations(
            settings,
            status_arg=self.get_argument("status", None),
            page=page,
            page_size=page_size,
            offset=offset,
        )
        self.write_json(success(data))


class AdminReservationDetailHandler(BaseHandler):
    async def get(self, reservation_id: str) -> None:
        await self.require_admin()
        settings = self.application.settings["app_settings"]
        reservation = await reservation_service.get_admin_reservation(settings, int(reservation_id))
        self.write_json(success(reservation))


class AdminReservationCancelHandler(BaseHandler):
    async def put(self, reservation_id: str) -> None:
        await self.require_admin()
        settings = self.application.settings["app_settings"]
        reservation = await reservation_service.admin_cancel_reservation(settings, int(reservation_id))
        self.write_json(success(reservation))


class AdminAnnouncementsHandler(BaseHandler):
    async def get(self) -> None:
        await self.require_admin()
        settings = self.application.settings["app_settings"]
        page, page_size, offset = pagination(self)
        data = await announcement_service.list_admin_announcements(
            settings,
            status_arg=self.get_argument("status", None),
            page=page,
            page_size=page_size,
            offset=offset,
        )
        self.write_json(success(data))

    async def post(self) -> None:
        current_user = await self.require_admin()
        settings = self.application.settings["app_settings"]
        announcement = await announcement_service.create_announcement(
            settings,
            current_user=current_user,
            body=self.get_json_body(),
        )
        self.write_json(success(announcement))


class AdminAnnouncementDetailHandler(BaseHandler):
    async def put(self, announcement_id: str) -> None:
        await self.require_admin()
        settings = self.application.settings["app_settings"]
        announcement = await announcement_service.update_announcement(
            settings,
            int(announcement_id),
            self.get_json_body(),
        )
        self.write_json(success(announcement))

    async def delete(self, announcement_id: str) -> None:
        await self.require_admin()
        settings = self.application.settings["app_settings"]
        announcement = await announcement_service.update_announcement_status(
            settings,
            int(announcement_id),
            {"status": 0},
        )
        self.write_json(success(announcement))


class AdminAnnouncementStatusHandler(BaseHandler):
    async def put(self, announcement_id: str) -> None:
        await self.require_admin()
        settings = self.application.settings["app_settings"]
        announcement = await announcement_service.update_announcement_status(
            settings,
            int(announcement_id),
            self.get_json_body(),
        )
        self.write_json(success(announcement))


class AdminConfigsHandler(BaseHandler):
    async def get(self) -> None:
        await self.require_admin()
        settings = self.application.settings["app_settings"]
        configs = await config_service.list_configs(settings)
        self.write_json(success(configs))


class AdminConfigDetailHandler(BaseHandler):
    async def put(self, config_key: str) -> None:
        current_user = await self.require_admin()
        settings = self.application.settings["app_settings"]
        body = self.get_json_body()
        config = await config_service.update_config(
            settings,
            config_key=config_key,
            config_value=body.get("config_value"),
            updated_by=current_user["id"],
        )
        self.write_json(success(config))
