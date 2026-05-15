from handlers.base import BaseHandler
from services import (
    admin_user_service,
    announcement_service,
    config_service,
    court_service,
    operation_log_service,
    reservation_service,
    statistics_service,
)
from utils.query import pagination
from utils.response import success


async def _record_admin_log(
    handler: BaseHandler,
    current_user: dict,
    *,
    module: str,
    action: str,
    target_type: str | None,
    target_id: int | None,
    detail: dict,
) -> None:
    settings = handler.application.settings["app_settings"]
    await operation_log_service.record_admin_operation(
        settings,
        current_user=current_user,
        module=module,
        action=action,
        target_type=target_type,
        target_id=target_id,
        detail=detail,
        ip=handler.request.remote_ip,
    )


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
        current_user = await self.require_admin()
        settings = self.application.settings["app_settings"]
        user = await admin_user_service.create_user(settings, self.get_json_body())
        await _record_admin_log(
            self,
            current_user,
            module="user",
            action="create",
            target_type="user",
            target_id=user["id"],
            detail={"username": user["username"], "role": user["role"], "status": user["status"]},
        )
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
        await _record_admin_log(
            self,
            current_user,
            module="user",
            action="status",
            target_type="user",
            target_id=user["id"],
            detail={"username": user["username"], "status": user["status"]},
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
        await _record_admin_log(
            self,
            current_user,
            module="user",
            action="role",
            target_type="user",
            target_id=user["id"],
            detail={"username": user["username"], "role": user["role"]},
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
        current_user = await self.require_admin()
        settings = self.application.settings["app_settings"]
        court = await court_service.create_court(settings, self.get_json_body())
        await _record_admin_log(
            self,
            current_user,
            module="court",
            action="create",
            target_type="court",
            target_id=court["id"],
            detail={"court_no": court["court_no"], "court_name": court["court_name"], "status": court["status"]},
        )
        self.write_json(success(court))


class AdminCourtDetailHandler(BaseHandler):
    async def put(self, court_id: str) -> None:
        current_user = await self.require_admin()
        settings = self.application.settings["app_settings"]
        court = await court_service.update_court(settings, int(court_id), self.get_json_body())
        await _record_admin_log(
            self,
            current_user,
            module="court",
            action="update",
            target_type="court",
            target_id=court["id"],
            detail={"court_no": court["court_no"], "court_name": court["court_name"], "status": court["status"]},
        )
        self.write_json(success(court))


class AdminCourtStatusHandler(BaseHandler):
    async def put(self, court_id: str) -> None:
        current_user = await self.require_admin()
        settings = self.application.settings["app_settings"]
        court = await court_service.update_court_status(settings, int(court_id), self.get_json_body())
        await _record_admin_log(
            self,
            current_user,
            module="court",
            action="status",
            target_type="court",
            target_id=court["id"],
            detail={"court_no": court["court_no"], "status": court["status"]},
        )
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
        current_user = await self.require_admin()
        settings = self.application.settings["app_settings"]
        reservation = await reservation_service.admin_cancel_reservation(settings, int(reservation_id))
        await _record_admin_log(
            self,
            current_user,
            module="reservation",
            action="cancel",
            target_type="reservation",
            target_id=reservation["id"],
            detail={
                "reservation_no": reservation["reservation_no"],
                "username": reservation.get("username"),
                "court_no": reservation.get("court_no"),
            },
        )
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
        await _record_admin_log(
            self,
            current_user,
            module="announcement",
            action="create",
            target_type="announcement",
            target_id=announcement["id"],
            detail={"title": announcement["title"], "status": announcement["status"]},
        )
        self.write_json(success(announcement))


class AdminAnnouncementDetailHandler(BaseHandler):
    async def put(self, announcement_id: str) -> None:
        current_user = await self.require_admin()
        settings = self.application.settings["app_settings"]
        announcement = await announcement_service.update_announcement(
            settings,
            int(announcement_id),
            self.get_json_body(),
        )
        await _record_admin_log(
            self,
            current_user,
            module="announcement",
            action="update",
            target_type="announcement",
            target_id=announcement["id"],
            detail={"title": announcement["title"], "status": announcement["status"]},
        )
        self.write_json(success(announcement))

    async def delete(self, announcement_id: str) -> None:
        current_user = await self.require_admin()
        settings = self.application.settings["app_settings"]
        announcement = await announcement_service.update_announcement_status(
            settings,
            int(announcement_id),
            {"status": 0},
        )
        await _record_admin_log(
            self,
            current_user,
            module="announcement",
            action="hide",
            target_type="announcement",
            target_id=announcement["id"],
            detail={"title": announcement["title"], "status": announcement["status"]},
        )
        self.write_json(success(announcement))


class AdminAnnouncementStatusHandler(BaseHandler):
    async def put(self, announcement_id: str) -> None:
        current_user = await self.require_admin()
        settings = self.application.settings["app_settings"]
        announcement = await announcement_service.update_announcement_status(
            settings,
            int(announcement_id),
            self.get_json_body(),
        )
        await _record_admin_log(
            self,
            current_user,
            module="announcement",
            action="status",
            target_type="announcement",
            target_id=announcement["id"],
            detail={"title": announcement["title"], "status": announcement["status"]},
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
        await _record_admin_log(
            self,
            current_user,
            module="config",
            action="update",
            target_type="config",
            target_id=config["id"],
            detail={"config_key": config["config_key"], "config_value": config["config_value"]},
        )
        self.write_json(success(config))


class AdminStatisticsOverviewHandler(BaseHandler):
    async def get(self) -> None:
        await self.require_admin()
        settings = self.application.settings["app_settings"]
        data = await statistics_service.get_overview(
            settings,
            date_from_arg=self.get_argument("date_from", None),
            date_to_arg=self.get_argument("date_to", None),
        )
        self.write_json(success(data))


class AdminStatisticsCourtsHandler(BaseHandler):
    async def get(self) -> None:
        await self.require_admin()
        settings = self.application.settings["app_settings"]
        data = await statistics_service.list_court_statistics(
            settings,
            date_from_arg=self.get_argument("date_from", None),
            date_to_arg=self.get_argument("date_to", None),
        )
        self.write_json(success(data))


class AdminStatisticsTimeSlotsHandler(BaseHandler):
    async def get(self) -> None:
        await self.require_admin()
        settings = self.application.settings["app_settings"]
        data = await statistics_service.list_time_slot_statistics(
            settings,
            date_from_arg=self.get_argument("date_from", None),
            date_to_arg=self.get_argument("date_to", None),
            limit_arg=self.get_argument("limit", None),
        )
        self.write_json(success(data))


class AdminStatisticsUsersHandler(BaseHandler):
    async def get(self) -> None:
        await self.require_admin()
        settings = self.application.settings["app_settings"]
        data = await statistics_service.list_user_statistics(
            settings,
            date_from_arg=self.get_argument("date_from", None),
            date_to_arg=self.get_argument("date_to", None),
            limit_arg=self.get_argument("limit", None),
        )
        self.write_json(success(data))


class AdminOperationLogsHandler(BaseHandler):
    async def get(self) -> None:
        await self.require_admin()
        settings = self.application.settings["app_settings"]
        page, page_size, offset = pagination(self)
        data = await operation_log_service.list_operation_logs(
            settings,
            module_arg=self.get_argument("module", None),
            action_arg=self.get_argument("action", None),
            username_arg=self.get_argument("username", None),
            date_from_arg=self.get_argument("date_from", None),
            date_to_arg=self.get_argument("date_to", None),
            page=page,
            page_size=page_size,
            offset=offset,
        )
        self.write_json(success(data))
