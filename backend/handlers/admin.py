from handlers.base import BaseHandler
from services import (
    admin_user_service,
    announcement_service,
    community_service,
    config_service,
    court_service,
    event_service,
    notification_service,
    operation_log_service,
    reservation_service,
    shop_service,
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
            user_id=self.path_int(user_id, "用户ID"),
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
            user_id=self.path_int(user_id, "用户ID"),
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


class AdminUserMemberHandler(BaseHandler):
    async def put(self, user_id: str) -> None:
        current_user = await self.require_admin()
        settings = self.application.settings["app_settings"]
        user = await admin_user_service.update_user_member(
            settings,
            current_user=current_user,
            user_id=self.path_int(user_id, "用户ID"),
            body=self.get_json_body(),
        )
        await _record_admin_log(
            self,
            current_user,
            module="user",
            action="member",
            target_type="user",
            target_id=user["id"],
            detail={
                "username": user["username"],
                "member_level": user["member"]["level"],
                "balance_cents": user["member"]["balance_cents"],
                "points": user["member"]["points"],
                "expires_at": user["member"]["expires_at"],
            },
        )
        self.write_json(success(user))


class AdminUserPasswordHandler(BaseHandler):
    async def put(self, user_id: str) -> None:
        current_user = await self.require_admin()
        settings = self.application.settings["app_settings"]
        user = await admin_user_service.reset_user_password(
            settings,
            current_user=current_user,
            user_id=self.path_int(user_id, "用户ID"),
            body=self.get_json_body(),
        )
        await _record_admin_log(
            self,
            current_user,
            module="user",
            action="update",
            target_type="user",
            target_id=user["id"],
            detail={"username": user["username"], "field": "password"},
        )
        self.write_json(success(user, "密码已重置"))


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
            detail={
                "court_no": court["court_no"],
                "court_name": court["court_name"],
                "status": court["status"],
                "price_per_hour_cents": court["price_per_hour_cents"],
                "capacity": court["capacity"],
            },
        )
        self.write_json(success(court))


class AdminCourtDetailHandler(BaseHandler):
    async def put(self, court_id: str) -> None:
        current_user = await self.require_admin()
        settings = self.application.settings["app_settings"]
        court = await court_service.update_court(settings, self.path_int(court_id, "场地ID"), self.get_json_body())
        await _record_admin_log(
            self,
            current_user,
            module="court",
            action="update",
            target_type="court",
            target_id=court["id"],
            detail={
                "court_no": court["court_no"],
                "court_name": court["court_name"],
                "status": court["status"],
                "price_per_hour_cents": court["price_per_hour_cents"],
                "capacity": court["capacity"],
            },
        )
        self.write_json(success(court))


class AdminCourtStatusHandler(BaseHandler):
    async def put(self, court_id: str) -> None:
        current_user = await self.require_admin()
        settings = self.application.settings["app_settings"]
        court = await court_service.update_court_status(settings, self.path_int(court_id, "场地ID"), self.get_json_body())
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
            username_arg=self.get_argument("username", None),
            court_id_arg=self.get_argument("court_id", None),
            date_from_arg=self.get_argument("date_from", None),
            date_to_arg=self.get_argument("date_to", None),
        )
        self.write_json(success(data))


class AdminReservationDetailHandler(BaseHandler):
    async def get(self, reservation_id: str) -> None:
        await self.require_admin()
        settings = self.application.settings["app_settings"]
        reservation = await reservation_service.get_admin_reservation(settings, self.path_int(reservation_id, "预约ID"))
        self.write_json(success(reservation))


class AdminReservationCancelHandler(BaseHandler):
    async def put(self, reservation_id: str) -> None:
        current_user = await self.require_admin()
        settings = self.application.settings["app_settings"]
        reservation = await reservation_service.admin_cancel_reservation(
            settings,
            self.path_int(reservation_id, "预约ID"),
            current_user=current_user,
        )
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
            self.path_int(announcement_id, "公告ID"),
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
            self.path_int(announcement_id, "公告ID"),
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
            self.path_int(announcement_id, "公告ID"),
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


class AdminNotificationBroadcastHandler(BaseHandler):
    async def post(self) -> None:
        current_user = await self.require_admin()
        settings = self.application.settings["app_settings"]
        data = await notification_service.broadcast_to_enabled_users(
            settings,
            current_user=current_user,
            body=self.get_json_body(),
        )
        await _record_admin_log(
            self,
            current_user,
            module="notification",
            action="broadcast",
            target_type="notification",
            target_id=None,
            detail={"sent_count": data["sent_count"]},
        )
        self.write_json(success(data, "通知已发送"))


class AdminEventsHandler(BaseHandler):
    async def get(self) -> None:
        await self.require_admin()
        settings = self.application.settings["app_settings"]
        page, page_size, offset = pagination(self)
        data = await event_service.list_admin_events(
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
        event = await event_service.create_event(
            settings,
            current_user=current_user,
            body=self.get_json_body(),
        )
        await _record_admin_log(
            self,
            current_user,
            module="event",
            action="create",
            target_type="event",
            target_id=event["id"],
            detail={"title": event["title"], "status": event["status"]},
        )
        self.write_json(success(event))


class AdminEventDetailHandler(BaseHandler):
    async def put(self, event_id: str) -> None:
        current_user = await self.require_admin()
        settings = self.application.settings["app_settings"]
        event = await event_service.update_event(settings, self.path_int(event_id, "活动ID"), self.get_json_body())
        await _record_admin_log(
            self,
            current_user,
            module="event",
            action="update",
            target_type="event",
            target_id=event["id"],
            detail={"title": event["title"], "status": event["status"], "capacity": event["capacity"]},
        )
        self.write_json(success(event))


class AdminEventStatusHandler(BaseHandler):
    async def put(self, event_id: str) -> None:
        current_user = await self.require_admin()
        settings = self.application.settings["app_settings"]
        event = await event_service.update_event_status(
            settings,
            current_user=current_user,
            event_id=self.path_int(event_id, "活动ID"),
            body=self.get_json_body(),
        )
        await _record_admin_log(
            self,
            current_user,
            module="event",
            action="status",
            target_type="event",
            target_id=event["id"],
            detail={"title": event["title"], "status": event["status"]},
        )
        self.write_json(success(event))


class AdminCommunityPostsHandler(BaseHandler):
    async def get(self) -> None:
        await self.require_admin()
        settings = self.application.settings["app_settings"]
        page, page_size, offset = pagination(self)
        data = await community_service.list_admin_posts(
            settings,
            status_arg=self.get_argument("status", None),
            page=page,
            page_size=page_size,
            offset=offset,
        )
        self.write_json(success(data))


class AdminCommunityPostHideHandler(BaseHandler):
    async def put(self, post_id: str) -> None:
        current_user = await self.require_admin()
        settings = self.application.settings["app_settings"]
        post = await community_service.admin_hide_post(settings, self.path_int(post_id, "动态ID"))
        await _record_admin_log(
            self,
            current_user,
            module="community",
            action="hide",
            target_type="community_post",
            target_id=post["id"],
            detail={"username": post.get("username"), "content": post.get("content")},
        )
        self.write_json(success(post, "动态已隐藏"))


class AdminShopProductsHandler(BaseHandler):
    async def get(self) -> None:
        await self.require_admin()
        settings = self.application.settings["app_settings"]
        page, page_size, offset = pagination(self)
        data = await shop_service.list_products(
            settings,
            status_arg=self.get_argument("status", None),
            keyword_arg=self.get_argument("keyword", None),
            page=page,
            page_size=page_size,
            offset=offset,
            public_only=False,
        )
        self.write_json(success(data))

    async def post(self) -> None:
        current_user = await self.require_admin()
        settings = self.application.settings["app_settings"]
        product = await shop_service.create_product(settings, self.get_json_body())
        await _record_admin_log(
            self,
            current_user,
            module="shop",
            action="create",
            target_type="shop_product",
            target_id=product["id"],
            detail={"product_no": product["product_no"], "product_name": product["product_name"]},
        )
        self.write_json(success(product))


class AdminShopProductDetailHandler(BaseHandler):
    async def put(self, product_id: str) -> None:
        current_user = await self.require_admin()
        settings = self.application.settings["app_settings"]
        product = await shop_service.update_product(settings, self.path_int(product_id, "商品ID"), self.get_json_body())
        await _record_admin_log(
            self,
            current_user,
            module="shop",
            action="update",
            target_type="shop_product",
            target_id=product["id"],
            detail={
                "product_no": product["product_no"],
                "product_name": product["product_name"],
                "stock": product["stock"],
            },
        )
        self.write_json(success(product))


class AdminShopProductStatusHandler(BaseHandler):
    async def put(self, product_id: str) -> None:
        current_user = await self.require_admin()
        settings = self.application.settings["app_settings"]
        product = await shop_service.update_product_status(settings, self.path_int(product_id, "商品ID"), self.get_json_body())
        await _record_admin_log(
            self,
            current_user,
            module="shop",
            action="status",
            target_type="shop_product",
            target_id=product["id"],
            detail={"product_no": product["product_no"], "status": product["status"]},
        )
        self.write_json(success(product))


class AdminShopOrdersHandler(BaseHandler):
    async def get(self) -> None:
        await self.require_admin()
        settings = self.application.settings["app_settings"]
        page, page_size, offset = pagination(self)
        data = await shop_service.list_admin_orders(
            settings,
            status_arg=self.get_argument("status", None),
            username_arg=self.get_argument("username", None),
            page=page,
            page_size=page_size,
            offset=offset,
        )
        self.write_json(success(data))


class AdminShopOrderDetailHandler(BaseHandler):
    async def get(self, order_id: str) -> None:
        await self.require_admin()
        settings = self.application.settings["app_settings"]
        order = await shop_service.get_admin_order(settings, self.path_int(order_id, "订单ID"))
        self.write_json(success(order))


class AdminShopOrderCompleteHandler(BaseHandler):
    async def put(self, order_id: str) -> None:
        current_user = await self.require_admin()
        settings = self.application.settings["app_settings"]
        order = await shop_service.complete_order(
            settings,
            current_user=current_user,
            order_id=self.path_int(order_id, "订单ID"),
        )
        await _record_admin_log(
            self,
            current_user,
            module="shop",
            action="complete",
            target_type="shop_order",
            target_id=order["id"],
            detail={"order_no": order["order_no"], "username": order.get("username")},
        )
        self.write_json(success(order, "订单已完成"))


class AdminShopOrderCancelHandler(BaseHandler):
    async def put(self, order_id: str) -> None:
        current_user = await self.require_admin()
        settings = self.application.settings["app_settings"]
        order = await shop_service.admin_cancel_order(
            settings,
            current_user=current_user,
            order_id=self.path_int(order_id, "订单ID"),
        )
        await _record_admin_log(
            self,
            current_user,
            module="shop",
            action="cancel",
            target_type="shop_order",
            target_id=order["id"],
            detail={"order_no": order["order_no"], "username": order.get("username")},
        )
        self.write_json(success(order, "订单已取消并退款"))


class AdminShopOrderRefundRejectHandler(BaseHandler):
    async def put(self, order_id: str) -> None:
        current_user = await self.require_admin()
        settings = self.application.settings["app_settings"]
        order = await shop_service.reject_refund_request(
            settings,
            current_user=current_user,
            order_id=self.path_int(order_id, "订单ID"),
            body=self.get_json_body(),
        )
        await _record_admin_log(
            self,
            current_user,
            module="shop",
            action="refund_reject",
            target_type="shop_order",
            target_id=order["id"],
            detail={"order_no": order["order_no"], "username": order.get("username"), "reason": order.get("refund_reject_reason")},
        )
        self.write_json(success(order, "退款申请已驳回"))


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
