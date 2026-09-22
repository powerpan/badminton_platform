from datetime import date, datetime, timedelta
from pathlib import Path
import importlib.util
import unittest
from unittest.mock import AsyncMock, patch

from repositories import reservation_repository
from services import reservation_service

spec = importlib.util.spec_from_file_location('create_demo', Path(__file__).resolve().parents[2] / 'scripts/create_demo.py')
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)


class ReservationSummaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_summary_scopes_each_query_to_current_user_and_orders_earliest(self):
        fetch = AsyncMock(side_effect=[{'id': 2}, {'id': 3}, {'total': 1}])
        with patch.object(reservation_repository, 'fetch_one', fetch):
            data = await reservation_repository.get_user_summary(None, user_id=72)
        self.assertEqual(data, {'upcoming': {'id': 2}, 'pending': {'id': 3}, 'pending_count': 1})
        for call in fetch.call_args_list:
            self.assertEqual(call.args[2], (72,))
            self.assertIn('r.user_id = %s', call.args[1])
        self.assertIn('r.end_time) > NOW()', fetch.call_args_list[0].args[1])
        self.assertIn('ORDER BY r.reserve_date, r.start_time, r.id LIMIT 1', fetch.call_args_list[0].args[1])
        self.assertIn('ro.expires_at > NOW()', fetch.call_args_list[1].args[1])
        self.assertIn('ORDER BY ro.expires_at', fetch.call_args_list[1].args[1])

    async def test_empty_summary_is_explicit_and_time_values_are_normalized(self):
        row = {'id': 1, 'start_time': timedelta(hours=18), 'end_time': timedelta(hours=19),
               'order_expires_at': datetime(2026, 9, 16, 19, 15)}
        with patch.object(reservation_service, 'refresh_reservation_statuses', AsyncMock()), \
             patch.object(reservation_repository, 'get_user_summary', AsyncMock(return_value={'upcoming': None, 'pending': row, 'pending_count': 1})):
            result = await reservation_service.my_reservation_summary(None, current_user={'id': 4})
        self.assertIsNone(result['upcoming'])
        self.assertEqual(result['pending']['start_time'], '18:00')
        self.assertIn('T19:15:00', result['pending']['order_expires_at'])


class DemoDatasetTests(unittest.TestCase):
    def test_current_and_invalid_database_names_are_rejected(self):
        for name in ['badminton_platform', 'mysql', 'badminton_demo_', 'badminton_demo_x;DROP DATABASE x', 'badminton_demo_X']:
            with self.assertRaises(ValueError): demo.validate_database(name)
        self.assertEqual(demo.validate_database('badminton_demo_20260916'), 'badminton_demo_20260916')

    def test_relative_dates_cover_all_states_and_more_than_fifty_rows(self):
        today = date(2027, 2, 3)
        dataset = demo.build_dataset(today, datetime(2027, 2, 3, 12))
        rows = dataset['reservation']
        self.assertEqual(len(rows), 58)
        self.assertEqual(len({r['reservation_no'] for r in rows}), 58)
        self.assertEqual({r['status'] for r in rows}, {'pending', 'confirmed', 'completed', 'canceled', 'expired'})
        upcoming = [r for r in rows if r['status'] == 'confirmed']
        self.assertGreater(upcoming[0]['reserve_date'], upcoming[1]['reserve_date'])
        self.assertEqual(min(r['reserve_date'] for r in upcoming), today + timedelta(days=1))
        for event in dataset['club_event']:
            self.assertLess(event['registration_deadline'], event['start_at'])
            self.assertLess(event['start_at'], event['end_at'])
            self.assertGreater(event['registration_deadline'].date(), today)
        paid_count = len([r for r in rows if r['status'] in ('confirmed', 'completed')])
        self.assertGreater(1000000 - paid_count * 12000, 0)


if __name__ == '__main__': unittest.main()
