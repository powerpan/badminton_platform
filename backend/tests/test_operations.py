from datetime import date, datetime, time, timedelta
from types import SimpleNamespace
from random import Random
import unittest
from utils.booking_operations import rank_windows, window, price, validate_attendance
from utils.response import ApiError
from services.operations_statistics_service import aggregate
from services.booking_operations_service import date_range


class OperationsRulesTests(unittest.TestCase):
    def test_window_rejects_past_offgrid_and_overlong(self):
        rules = SimpleNamespace(advance_reservation_days=7, business_start_time=time(9), business_end_time=time(21), slot_interval_minutes=30, max_reservation_hours=2)
        base = {'court_id':1,'reserve_date':'2026-09-17','start_time':'18:00','end_time':'20:00'}
        now = datetime(2026,9,16,12)
        self.assertEqual(window(base,rules,now)['end_time'],time(20))
        for patch in [{'reserve_date':'2026-09-15'},{'start_time':'18:15'},{'end_time':'20:30'},{'reserve_date':'2026-09-25'}]:
            with self.assertRaises(ApiError): window({**base,**patch},rules,now)

    def test_target_date_membership_and_integer_price(self):
        court={'price_per_hour_cents':10001}
        account={'member_level':'gold','expires_at':date(2026,9,16)}
        target={'reserve_date':date(2026,9,16),'start_time':'18:00','end_time':'18:30'}
        self.assertEqual(price(court,account,target)['payable_amount_cents'],4500)
        self.assertEqual(price(court,account,{**target,'reserve_date':date(2026,9,17)})['payable_amount_cents'],5000)

    def test_attendance_window_and_no_show_are_distinct(self):
        r={'status':'confirmed','reserve_date':date(2026,9,16),'start_time':time(18),'end_time':time(19)}
        validate_attendance(r,'checked_in',datetime(2026,9,16,17,30))
        validate_attendance(r,'no_show',datetime(2026,9,16,19))
        for outcome,now in [('checked_in',datetime(2026,9,16,17,29)),('checked_in',datetime(2026,9,16,19)),('no_show',datetime(2026,9,16,18,59))]:
            with self.assertRaises(ApiError): validate_attendance(r,outcome,now)

    def test_range_includes_at_most_366_dates(self):
        date_range('2026-01-01','2027-01-01')
        with self.assertRaises(ApiError): date_range('2026-01-01','2027-01-02')


class RecommendationTests(unittest.TestCase):
    def test_prefix_matches_naive_availability_across_seeded_cases(self):
        random=Random(7531)
        courts=[{'id':n,'court_no':f'A{n:02}','court_name':str(n),'price_per_hour_cents':12000} for n in range(1,5)]
        for interval in (15,30,60):
            for _ in range(30):
                slot_map={}
                for c in courts:
                    slot_map[c['id']]=[{'start_time':f'{m//60:02}:{m%60:02}', 'end_time':f'{(m+interval)//60:02}:{(m+interval)%60:02}',
                        'status':random.choice(['available']*4+['reserved','maintenance','locked'])} for m in range(540,1260,interval)]
                for duration in (60,120):
                    candidates=rank_windows(courts,slot_map,day=date(2026,9,17),earliest='09:00',duration=duration,interval=interval,account={},limit=10000)
                    expected=set()
                    for court in courts:
                        slots=slot_map[court['id']]
                        for i in range(len(slots)-duration//interval+1):
                            part=slots[i:i+duration//interval]
                            if all(s['status']=='available' for s in part): expected.add((court['id'],part[0]['start_time'],part[-1]['end_time']))
                    self.assertEqual({(c['court_id'],c['start_time'],c['end_time']) for c in candidates},expected)

    def test_deterministic_preference_price_and_empty(self):
        courts=[{'id':n,'court_no':f'A{n}','court_name':str(n),'price_per_hour_cents':10000+n*1000} for n in (3,1,2)]
        slots=[{'start_time':'18:00','end_time':'19:00','status':'available'}, {'start_time':'19:00','end_time':'20:00','status':'available'}]
        kwargs=dict(day=date(2026,9,17),earliest='18:00',duration=120,interval=60,account={},preferred=3)
        result=rank_windows(courts,{n:slots for n in (1,2,3)},**kwargs)
        self.assertEqual([r['court_id'] for r in result],[3,1,2])
        self.assertEqual(result,rank_windows(list(reversed(courts)),{n:slots for n in (1,2,3)},**kwargs))
        self.assertEqual(rank_windows(courts,{1:slots},**{**kwargs,'earliest':'19:00'}),[])

    def test_tied_candidates_avoid_single_slot_fragment(self):
        courts=[{'id':n,'court_no':f'A{n}','court_name':str(n),'price_per_hour_cents':10000} for n in (1,2)]
        def slots(first):
            return [{'start_time':f'{h:02}:00','end_time':f'{h+1:02}:00','status':'available' if first <= h < 19 else 'reserved'} for h in range(9,21)]
        result=rank_windows(courts,{1:slots(17),2:slots(16)},day=date(2026,9,17),earliest='18:00',duration=60,interval=60,account={})
        self.assertEqual([r['court_id'] for r in result],[2,1])
        # Equal time and price: court 2 leaves a two-hour window, court 1 only one slot.
        self.assertEqual([r['start_time'] for r in result],['18:00','18:00'])


class OperationsStatisticsTests(unittest.TestCase):
    def test_minutes_cash_dates_and_unknown_attendance(self):
        start=date(2026,9,16)
        rows=[{'reserve_date':start,'start_time':time(18,30),'end_time':time(20),'status':'completed','attendance_outcome':outcome} for outcome in ['checked_in','no_show',None]]
        rows.append({**rows[0],'status':'canceled'})
        result=aggregate(rows,[{'balance_change_cents':-12000},{'balance_change_cents':2000},{'balance_change_cents':-500}],start,start+timedelta(days=1),datetime(2026,9,18))
        self.assertEqual(result['daily'][0]['booked_minutes'],270)
        self.assertEqual(result['hourly'][18]['booked_minutes'],90)
        self.assertEqual(result['hourly'][19]['booked_minutes'],180)
        self.assertEqual(result['daily'][1]['total'],0)
        self.assertEqual(result['net_cents'],10500)
        self.assertEqual(result['cancellation_rate'],25)
        self.assertEqual(result['attendance_rate'],50)
        self.assertEqual(result['attendance_coverage'],66.67)
        self.assertEqual(result['unrecorded'],1)

    def test_empty_is_unknown_not_zero_attendance(self):
        result=aggregate([],[],date(2026,9,16),date(2026,9,16))
        self.assertIsNone(result['attendance_rate'])
        self.assertIsNone(result['cancellation_rate'])
        self.assertEqual(result['net_cents'],0)
