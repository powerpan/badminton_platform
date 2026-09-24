from datetime import datetime, time
from types import SimpleNamespace
import unittest

from utils.staff_booking import parse_target, validate_window, original_price, request_key
from utils.response import ApiError


class WalkInRulesTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026,10,1,14,10)
        self.rules = SimpleNamespace(business_start_time=time(9),business_end_time=time(21),
            slot_interval_minutes=60,max_reservation_hours=2,reservation_payment_timeout_minutes=15)
        self.target = parse_target({'court_id':1,'reserve_date':'2026-10-01','start_time':'14:00','end_time':'15:00'})

    def test_walkin_current_hour_is_full_price_without_points(self):
        self.assertEqual(validate_window(self.target,self.rules,self.now),datetime(2026,10,1,14,25))
        cost = original_price({'price_per_hour_cents':12000},self.target)
        self.assertEqual((cost['payable_amount_cents'],cost['discount_rate'],cost['points_awarded']),(12000,100,0))
        self.rules.slot_interval_minutes=30
        half={**self.target,'end_time':time(14,30)}
        self.assertEqual(original_price({'price_per_hour_cents':10001},half)['payable_amount_cents'],5000)
        self.assertEqual(validate_window(half,self.rules,datetime(2026,10,1,14,25)),datetime(2026,10,1,14,30))

    def test_deadline_is_first_slot_end_even_for_two_hours(self):
        target = {**self.target,'end_time':time(16)}
        self.assertEqual(validate_window(target,self.rules,datetime(2026,10,1,14,55)),datetime(2026,10,1,15))
        for start in (time(13),time(15),time(14,10)):
            with self.subTest(start=start), self.assertRaises(ApiError):
                validate_window({**target,'start_time':start},self.rules,self.now)

    def test_extension_deadline_and_interval_boundaries(self):
        target = {**self.target,'start_time':time(15),'end_time':time(16)}
        self.assertEqual(validate_window(target,self.rules,datetime(2026,10,1,14,55),extension=True),datetime(2026,10,1,15))
        with self.assertRaises(ApiError): validate_window(target,self.rules,datetime(2026,10,1,15),extension=True)
        for end in (time(14,30),time(17),time(22)):
            with self.subTest(end=end), self.assertRaises(ApiError):
                validate_window({**self.target,'end_time':end},self.rules,self.now)

    def test_request_key_and_money_bounds(self):
        for value in ('',None,'short','a'*65,'空格 request'):
            with self.subTest(value=value), self.assertRaises(ApiError): request_key({'request_key':value})
        with self.assertRaises(ApiError): original_price({'price_per_hour_cents':2_147_483_648},self.target)


if __name__=='__main__': unittest.main()
