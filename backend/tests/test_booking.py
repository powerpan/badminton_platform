import asyncio
from contextlib import ExitStack
from datetime import date, datetime, time, timedelta
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from repositories import member_repository
from services import court_service, statistics_service
from services.config_service import public_reservation_rules
from services.maintenance_service import ReservationMaintenance
from services.reservation_service import _normalize_reservation
from services import redis_service
from utils.time_slots import overlaps


def rules(interval=60):
    return SimpleNamespace(business_start_time=time(9), business_end_time=time(21),
        slot_interval_minutes=interval, advance_reservation_days=10,
        max_reservation_hours=2, daily_reservation_limit=3, reservation_payment_timeout_minutes=15)


class IntervalTests(unittest.TestCase):
    def test_adjacency_does_not_overlap(self):
        self.assertFalse(overlaps("17:00", "18:00", "18:00", "20:00"))
        self.assertFalse(overlaps("20:00", "21:00", "18:00", "20:00"))

    def test_partial_and_contained_intervals(self):
        self.assertTrue(overlaps(time(18), time(19), timedelta(hours=18), timedelta(hours=20)))
        self.assertTrue(overlaps("17:30", "18:30", "18:00", "20:00"))

    def test_expiry_has_timezone(self):
        row = _normalize_reservation({"order_expires_at": datetime(2026, 9, 17, 18)})
        self.assertIsNotNone(datetime.fromisoformat(row["order_expires_at"]).tzinfo)


class CourtSlotTests(unittest.IsolatedAsyncioTestCase):
    async def slots(self, interval=60, reservations=None, locked=False, blocks=None):
        with ExitStack() as stack:
            values = {
                "reservation_repository.expire_pending_reservation_orders": 0,
                "reservation_repository.complete_finished_reservations": 0,
                "booking_operations_repository.list_blocks": blocks or [],
                "court_repository.get_court_by_id": {"id": 1, "status": 1, "price_per_hour_cents": 12000, "capacity": 4},
                "get_reservation_rules": rules(interval),
                "reservation_repository.list_reservations_for_court_date": reservations or [],
            }
            for name, result in values.items():
                stack.enter_context(patch("services.court_service." + name, new=AsyncMock(return_value=result)))
            locks = stack.enter_context(patch("services.court_service.locks_exist", new=AsyncMock(side_effect=lambda _settings, keys: [locked] * len(keys))))
            result = await court_service.get_slots(None, court_id=1, date_arg=(date.today() + timedelta(days=1)).isoformat())
            self.assertEqual(locks.await_count, 1)
            return result["slots"]

    async def test_two_hour_booking_occupies_both_slots(self):
        slots = await self.slots(reservations=[{"start_time": time(18), "end_time": time(20)}])
        by_start = {slot["start_time"]: slot["status"] for slot in slots}
        self.assertEqual([by_start[x] for x in ["17:00", "18:00", "19:00", "20:00"]],
                         ["available", "reserved", "reserved", "available"])

    async def test_half_hour_price_and_partial_overlap(self):
        slots = await self.slots(30, [{"start_time": time(18, 15), "end_time": time(19, 15)}])
        self.assertTrue(all(slot["price_cents"] == 6000 for slot in slots))
        self.assertEqual([slot["start_time"] for slot in slots if slot["status"] == "reserved"], ["18:00", "18:30", "19:00"])

    async def test_transient_locks_display_locked(self):
        self.assertTrue(all(slot["status"] == "locked" for slot in await self.slots(locked=True)))

    async def test_maintenance_reason_and_released_block(self):
        block = {"status": "active", "start_time": time(18), "end_time": time(20), "reason": "地胶维护"}
        slots = await self.slots(blocks=[block])
        maintained = [s for s in slots if s["status"] == "maintenance"]
        self.assertEqual([s["start_time"] for s in maintained], ["18:00", "19:00"])
        self.assertTrue(all(s["unavailable_reason"] == "地胶维护" for s in maintained))
        self.assertTrue(all(s["status"] == "available" for s in await self.slots(blocks=[{**block, "status": "released"}])))

    async def test_rules_include_full_configured_date_range(self):
        with patch("services.config_service.get_reservation_rules", new=AsyncMock(return_value=rules())):
            result = await public_reservation_rules(None)
        self.assertEqual((date.fromisoformat(result["max_date"]) - date.fromisoformat(result["min_date"])).days, 10)
        self.assertEqual(result["max_reservation_minutes"], 120)


class StatisticsTests(unittest.IsolatedAsyncioTestCase):
    async def calculate(self, interval=60, enabled=1, maintenance=0):
        row = {"id": 1, "court_no": "A01", "court_name": "Test", "status": enabled,
               "reservation_count": 1, "active_count": 1, "booked_hours": 2}
        with ExitStack() as stack:
            values = {"refresh_reservation_statuses": 0, "get_reservation_rules": rules(interval),
                "statistics_repository.get_user_counts": {"total_users": 1, "enabled_users": 1, "admin_users": 0},
                "statistics_repository.get_court_counts": {"total_courts": 1, "enabled_courts": enabled},
                "statistics_repository.get_reservation_status_counts": {"total": 1, "confirmed": 1},
                "statistics_repository.count_today_reservations": 1,
                "statistics_repository.count_active_users": 1,
                "statistics_repository.list_court_usage": [row],
                "statistics_repository.list_block_minutes": [{"court_id": 1, "minutes": maintenance}]}
            for name, result in values.items():
                stack.enter_context(patch("services.statistics_service." + name, new=AsyncMock(return_value=result)))
            dates = {"date_from_arg": "2026-09-17", "date_to_arg": "2026-09-17"}
            return await statistics_service.get_overview(None, **dates), await statistics_service.list_court_statistics(None, **dates)

    async def test_duration_based_rate_is_consistent(self):
        overview, courts = await self.calculate()
        self.assertEqual(overview["utilization_rate"], 16.67)
        self.assertEqual(courts["items"][0]["usage_rate"], 16.67)
        self.assertEqual(overview["occupied_minutes"], 120)

    async def test_rate_does_not_depend_on_slot_granularity(self):
        overview, courts = await self.calculate(interval=30)
        self.assertEqual(overview["utilization_rate"], 16.67)
        self.assertEqual(overview["occupied_slots"], 4)
        self.assertEqual(courts["items"][0]["usage_rate"], 16.67)

    async def test_maintenance_reduces_capacity_in_both_reports(self):
        overview, courts = await self.calculate(maintenance=120)
        self.assertEqual(overview["capacity_minutes"], 600)
        self.assertEqual(overview["maintenance_minutes"], 120)
        self.assertEqual(overview["utilization_rate"], 20)
        self.assertEqual(courts["items"][0]["usage_rate"], 20)

    async def test_no_enabled_capacity(self):
        overview, courts = await self.calculate(enabled=0)
        self.assertEqual(overview["utilization_rate"], 0)
        self.assertEqual(courts["items"][0]["usage_rate"], 0)


class BalanceAndRedisTests(unittest.IsolatedAsyncioTestCase):
    async def test_available_balance_excludes_pending_amount(self):
        with patch("repositories.member_repository.fetch_one", new=AsyncMock(return_value={"balance_cents": 50000, "pending_amount_cents": 12000})):
            result = await member_repository.get_booking_balance(None, 1)
        self.assertEqual(result["available_balance_cents"], 38000)
        self.assertEqual(result["balance_cents"], 50000)

    async def test_missing_account_and_negative_availability(self):
        for row in (None, {"balance_cents": 1000, "pending_amount_cents": 2000}):
            with patch("repositories.member_repository.fetch_one", new=AsyncMock(return_value=row)):
                self.assertEqual((await member_repository.get_booking_balance(None, 1))["available_balance_cents"], 0)

    async def test_batch_lock_query(self):
        client = AsyncMock()
        client.mget.return_value = [None, "owner", ""]
        with patch("services.redis_service.get_redis_client", return_value=client):
            self.assertEqual(await redis_service.locks_exist(None, ["a", "b", "c"]), [False, True, True])
            self.assertEqual(await redis_service.locks_exist(None, []), [])
        client.mget.assert_awaited_once()
        client.aclose.assert_not_awaited()


class BookingInputTests(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_payment_inputs_never_create_or_charge(self):
        from services import reservation_service as service
        from repositories import customer_booking_repository as online
        from utils.response import ApiError
        body={'court_id':1,'reserve_date':str(date.today()+timedelta(days=1)),
              'start_time':'18:00','end_time':'19:00','expected_amount_cents':12000}
        with patch.object(online,'create',AsyncMock()) as create:
            for extra in ({'pay_method':'alipay_live'}, {'expected_amount_cents':True},
                          {'expected_amount_cents':-1}, {'expected_amount_cents':2_147_483_648},
                          {'request_key':'short'}):
                with self.subTest(extra=extra), self.assertRaises(ApiError):
                    await service.create_reservation(None,current_user={'id':2},body={**body,**extra})
            create.assert_not_awaited()


class MaintenanceTests(unittest.IsolatedAsyncioTestCase):
    async def test_periodic_cleanup_runs_without_http_requests(self):
        entered = asyncio.Event()
        async def cleanup(_settings):
            entered.set()
        maintenance = ReservationMaintenance(None, interval_ms=10)
        with patch("services.maintenance_service.refresh_reservation_statuses", new=AsyncMock(side_effect=cleanup)):
            maintenance.start()
            try:
                await asyncio.wait_for(entered.wait(), timeout=1)
            finally:
                await maintenance.stop()

    async def test_cleanup_does_not_overlap_and_stop_waits(self):
        entered, release = asyncio.Event(), asyncio.Event()
        async def cleanup(_settings):
            entered.set()
            await release.wait()
        maintenance = ReservationMaintenance(None)
        with patch("services.maintenance_service.refresh_reservation_statuses", new=AsyncMock(side_effect=cleanup)) as refresh:
            task = asyncio.create_task(maintenance.run())
            await entered.wait()
            await maintenance.run()
            self.assertEqual(refresh.await_count, 1)
            stopped = asyncio.create_task(maintenance.stop())
            await asyncio.sleep(0)
            self.assertFalse(stopped.done())
            release.set()
            await task
            await stopped

    async def test_failure_does_not_disable_later_cleanup(self):
        maintenance = ReservationMaintenance(None)
        with patch("services.maintenance_service.refresh_reservation_statuses", new=AsyncMock(side_effect=[RuntimeError("offline"), 0])) as refresh:
            with self.assertLogs(level="ERROR"):
                await maintenance.run()
            await maintenance.run()
            self.assertEqual(refresh.await_count, 2)


if __name__ == "__main__":
    unittest.main()
