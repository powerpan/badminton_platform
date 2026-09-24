import unittest
from unittest.mock import AsyncMock, patch
from services import shop_service, reservation_service
from utils.response import ApiError


class CheckoutTests(unittest.IsolatedAsyncioTestCase):
    def test_confirmed_prices_required_and_duplicate_lines_agree(self):
        parse=shop_service._parse_order_items
        with self.assertRaises(ApiError):parse([{'product_id':1,'quantity':1}],require_prices=True)
        for items in [
            [{'product_id':1,'quantity':60,'expected_price_cents':1000}]*2,
            [{'product_id':1,'quantity':1,'expected_price_cents':n} for n in [1000,1500]],
            [{'product_id':1,'quantity':1,'expected_price_cents':True}],
        ]:
            with self.assertRaises(ApiError):parse(items,require_prices=True)
        self.assertEqual(parse([{'product_id':1,'quantity':2,'expected_price_cents':1000}]*2,require_prices=True),
                         [{'product_id':1,'quantity':4,'expected_price_cents':1000}])

    async def quote(self, products, balance):
        with patch.object(shop_service.shop_repository,'get_products_by_ids',AsyncMock(return_value=products)), \
             patch.object(shop_service.member_repository,'get_booking_balance',AsyncMock(return_value=balance)):
            return await shop_service.quote_order(None,current_user={'id':2},body={'items':[{'product_id':1,'quantity':2}]})

    async def test_quote_uses_server_price_stock_and_available_balance(self):
        product={'id':1,'product_name':'球','price_cents':1500,'stock':1,'status':1}
        q=await self.quote([product],{'balance_cents':9000,'pending_amount_cents':7000,'available_balance_cents':2000})
        self.assertEqual(q['total_amount_cents'],3000)
        self.assertEqual(q['items'][0]['quantity'],2)
        self.assertFalse(q['can_checkout'])
        self.assertEqual(len(q['issues']),2)
        self.assertIn('库存不足',q['issues'][0])
        q=await self.quote([{**product,'stock':10,'status':0}],{'balance_cents':9000,'pending_amount_cents':0,'available_balance_cents':9000})
        self.assertIn('已下架',q['issues'][0])

    async def test_quote_failure_cannot_create_order(self):
        with patch.object(shop_service.checkout,'create',AsyncMock()) as create:
            with self.assertRaises(ApiError):
                await shop_service.create_order(None,current_user={'id':2},body={'items':[{'product_id':1,'quantity':1}]})
            create.assert_not_awaited()

    async def test_latest_reservation_detail_is_owner_only(self):
        with patch.object(reservation_service,'refresh_reservation_statuses',AsyncMock()), \
             patch.object(reservation_service.reservation_repository,'get_reservation_detail',AsyncMock(return_value={'id':1,'user_id':3})):
            with self.assertRaises(ApiError) as error:
                await reservation_service.get_my_reservation(None,current_user={'id':2},reservation_id=1)
            self.assertEqual(error.exception.status_code,404)

if __name__=='__main__':unittest.main()
