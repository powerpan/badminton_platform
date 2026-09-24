from handlers.base import BaseHandler
from services import member_service
from repositories import member_repository
from utils.query import pagination
from utils.response import success


class BookingBalanceHandler(BaseHandler):
    async def get(self) -> None:
        current_user = await self.require_customer()
        data = await member_repository.get_booking_balance(self.application.settings["app_settings"], current_user["id"])
        self.write_json(success(data))


class MemberTransactionsHandler(BaseHandler):
    async def get(self) -> None:
        settings = self.application.settings["app_settings"]
        current_user = await self.require_customer()
        page, page_size, offset = pagination(self)
        data = await member_service.list_my_transactions(
            settings,
            current_user=current_user,
            type_arg=self.get_argument("transaction_type", None),
            page=page,
            page_size=page_size,
            offset=offset,
        )
        self.write_json(success(data))
