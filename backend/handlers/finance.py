from handlers.base import BaseHandler
from services import finance_service
from utils.response import success


class AdminTransactionsHandler(BaseHandler):
    async def get(self):
        await self.require_admin()
        fields=('date_from','date_to','business_type','entry_type','pay_method','status','customer','operator','order_no','page','page_size')
        params={field:self.get_argument(field,None) for field in fields}
        result=await finance_service.list_transactions(self.application.settings['app_settings'],params)
        self.set_header('Cache-Control','no-store')
        self.write_json(success(result))


class AdminTransactionDetailHandler(BaseHandler):
    async def get(self,record_type,record_id):
        await self.require_admin()
        result=await finance_service.detail(self.application.settings['app_settings'],record_type,self.path_int(record_id,'流水ID'))
        self.set_header('Cache-Control','no-store')
        self.write_json(success(result))
