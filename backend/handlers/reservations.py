from handlers.base import BaseHandler
from services import reservation_service
from utils.query import pagination
from utils.response import success


class ReservationsHandler(BaseHandler):
    async def post(self) -> None:
        settings = self.application.settings["app_settings"]
        current_user = await self.require_customer()
        reservation = await reservation_service.create_reservation(
            settings,
            current_user=current_user,
            body=self.get_json_body(),
        )
        self.write_json(success(reservation))


class MyReservationsHandler(BaseHandler):
    async def get(self) -> None:
        settings = self.application.settings["app_settings"]
        current_user = await self.require_customer()
        page, page_size, offset = pagination(self)
        data = await reservation_service.list_my_reservations(
            settings,
            current_user=current_user,
            status_arg=self.get_argument("status", None),
            page=page,
            page_size=page_size,
            offset=offset,
        )
        self.write_json(success(data))


class ReservationSummaryHandler(BaseHandler):
    async def get(self) -> None:
        current_user = await self.require_customer()
        data = await reservation_service.my_reservation_summary(
            self.application.settings["app_settings"], current_user=current_user,
        )
        self.write_json(success(data))


class CancelReservationHandler(BaseHandler):
    async def put(self, reservation_id: str) -> None:
        settings = self.application.settings["app_settings"]
        current_user = await self.require_customer()
        reservation = await reservation_service.cancel_my_reservation(
            settings,
            current_user=current_user,
            reservation_id=self.path_int(reservation_id, "预约ID"),
            body=self.get_json_body(),
        )
        self.write_json(success(reservation))


class ReservationOrderPayHandler(BaseHandler):
    async def put(self, order_id: str) -> None:
        settings = self.application.settings["app_settings"]
        current_user = await self.require_customer()
        reservation = await reservation_service.pay_reservation_order(
            settings,
            current_user=current_user,
            order_id=self.path_int(order_id, "订单ID"),
        )
        self.write_json(success(reservation, "支付成功，预约已确认"))


class MyReservationDetailHandler(BaseHandler):
    async def get(self, reservation_id: str) -> None:
        user = await self.require_customer()
        data = await reservation_service.get_my_reservation(self.application.settings['app_settings'], current_user=user, reservation_id=self.path_int(reservation_id, '预约ID'))
        self.write_json(success(data))
