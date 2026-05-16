from handlers.base import BaseHandler
from services import reservation_service
from utils.query import pagination
from utils.response import success


class ReservationsHandler(BaseHandler):
    async def post(self) -> None:
        settings = self.application.settings["app_settings"]
        current_user = await self.require_current_user()
        reservation = await reservation_service.create_reservation(
            settings,
            current_user=current_user,
            body=self.get_json_body(),
        )
        self.write_json(success(reservation))


class MyReservationsHandler(BaseHandler):
    async def get(self) -> None:
        settings = self.application.settings["app_settings"]
        current_user = await self.require_current_user()
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


class CancelReservationHandler(BaseHandler):
    async def put(self, reservation_id: str) -> None:
        settings = self.application.settings["app_settings"]
        current_user = await self.require_current_user()
        reservation = await reservation_service.cancel_my_reservation(
            settings,
            current_user=current_user,
            reservation_id=int(reservation_id),
        )
        self.write_json(success(reservation))


class ReservationOrderPayHandler(BaseHandler):
    async def put(self, order_id: str) -> None:
        settings = self.application.settings["app_settings"]
        current_user = await self.require_current_user()
        reservation = await reservation_service.pay_reservation_order(
            settings,
            current_user=current_user,
            order_id=int(order_id),
        )
        self.write_json(success(reservation, "支付成功，预约已确认"))
