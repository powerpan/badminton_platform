import json
from unittest.mock import AsyncMock, patch
import unittest
from types import SimpleNamespace
from datetime import date, datetime, timedelta, time

from tornado.testing import AsyncHTTPTestCase
from tornado.web import Application
from handlers.base import BaseHandler
from routes import build_routes
from services import auth_service, booking_operations_service as service, court_service
from utils.response import ApiError, success
from utils.roles import ROLES


class ProbeHandler(BaseHandler):
    async def get(self):
        self.write_json(success((await self.require_admin())['role']))


class StaffRoleHttpTests(AsyncHTTPTestCase):
    def get_app(self):
        return Application(build_routes() + [(r'/probe', ProbeHandler)], app_settings=SimpleNamespace(jwt_secret='test-only'))

    def setUp(self):
        super().setUp()
        self.actor = {'id': 20, 'username': 'qa_staff', 'role': 'frontdesk', 'status': 1}
        self.get_user = AsyncMock(side_effect=lambda *_: dict(self.actor))
        self.decode = patch('handlers.base.decode_access_token', return_value={'user_id': 20, 'role': 'admin'})
        self.users = patch('handlers.base.user_repository.get_user_by_id', self.get_user)
        self.decode.start(); self.users.start()

    def tearDown(self):
        self.users.stop(); self.decode.stop(); super().tearDown()

    def request(self, path, method='GET', body=None):
        return self.fetch(path, method=method, headers={'Authorization': 'Bearer test-role-token'},
                          body=None if method in ('GET', 'DELETE') else json.dumps(body or {}))

    def test_all_admin_endpoints_refuse_both_staff_roles(self):
        count = 0
        for role in ('frontdesk', 'maintenance', 'user'):
            self.actor['role'] = role
            for pattern, handler in build_routes():
                if not pattern.startswith('/api/admin/'): continue
                path = pattern.replace('([0-9]+)', '1').replace('([A-Za-z0-9_]+)', 'key').replace('([^/]+)', '1')
                for method in ('get', 'post', 'put', 'delete'):
                    if method not in handler.__dict__: continue
                    with self.subTest(role=role, method=method, path=path):
                        response = self.request(path, method.upper())
                        self.assertEqual(response.code, 403, response.body)
                        count += 1
        self.assertGreater(count, 120)

    def test_staff_cannot_consume_or_write_community_or_register_events(self):
        requests = [('/api/member/transactions','GET'),('/api/member/booking-balance','GET'),('/api/courts/1/slots?date=2026-10-01','GET'),('/api/reservations','POST'),('/api/reservations/my','GET'),
                    ('/api/reservations/1/cancel','PUT'),('/api/reservation-orders/1/pay','PUT'),
                    ('/api/reservations/1/reschedule','PUT'),('/api/reservations/1/reschedule/quote','POST'),
                    ('/api/shop/orders','POST'),('/api/shop/orders/quote','POST'),
                    ('/api/shop/orders/1/refund-request','PUT'),('/api/shop/orders/1/cancel','PUT'),('/api/shop/orders/1/pickup-code','GET'),
                    ('/api/community/posts','POST'),('/api/community/posts/1/hide','PUT'),
                    ('/api/events/1/register','POST'),('/api/events/1/cancel-registration','PUT')]
        for role in ('frontdesk','maintenance'):
            self.actor['role'] = role
            for path, method in requests:
                with self.subTest(role=role, path=path): self.assertEqual(self.request(path,method).code,403)

    def test_admin_booking_filters_reach_service_and_private_responses_are_not_cached(self):
        from services import reservation_service
        from urllib.parse import urlencode
        self.actor['role']='admin'
        query = {'source':'walk_in_extension','pay_method':'mock_alipay','operator':'前台甲',
                 'username':'散客_100%','order_no':'RF-test','page':'2','page_size':'7'}
        with patch.object(reservation_service,'list_admin_reservations',AsyncMock(return_value={'items':[],'total':0})) as call:
            response = self.request('/api/admin/reservations?' + urlencode(query))
            self.assertEqual(response.code,200)
            self.assertEqual(response.headers.get('Cache-Control'),'no-store')
            args=call.await_args.kwargs
            for key in ('source','pay_method','operator','username','order_no'):
                self.assertEqual(args[key+'_arg'],query[key])
            self.assertEqual((args['page'],args['page_size'],args['offset']),(2,7,7))
        with patch.object(reservation_service,'get_admin_reservation',AsyncMock(return_value={'id':1})):
            response=self.request('/api/admin/reservations/1')
            self.assertEqual(response.code,200)
            self.assertEqual(response.headers.get('Cache-Control'),'no-store')

    def test_financial_query_is_admin_only_with_typed_detail_and_private_response(self):
        from services import finance_service
        from urllib.parse import urlencode
        fields={'date_from':'2026-10-01','date_to':'2026-10-02','business_type':'recharge','entry_type':'recharge',
            'customer':'会员甲','operator':'desk','pay_method':'mock_alipay','status':'succeeded','order_no':'RC-test','page':'2','page_size':'5'}
        for role in ROLES:
            self.actor['role']=role
            with patch.object(finance_service,'list_transactions',AsyncMock(return_value={'items':[]})) as query:
                response=self.request('/api/admin/transactions?'+urlencode(fields))
                self.assertEqual(response.code,200 if role=='admin' else 403)
                if role=='admin':
                    self.assertEqual(query.await_args.args[1],fields)
                    self.assertEqual(response.headers.get('Cache-Control'),'no-store')
                else:query.assert_not_awaited()
            with patch.object(finance_service,'detail',AsyncMock(return_value={'record':{}})) as detail:
                response=self.request('/api/admin/transactions/payment/3')
                self.assertEqual(response.code,200 if role=='admin' else 403)
                if role=='admin':
                    self.assertEqual(detail.await_args.args[1:],('payment',3))
                    self.assertEqual(response.headers.get('Cache-Control'),'no-store')
                else:detail.assert_not_awaited()

    def test_pickup_staff_permissions_are_checked_before_lookup_and_redeem(self):
        from services import pickup_service
        for endpoint, function in (('lookup', 'lookup'), ('redeem', 'redeem')):
            with patch.object(pickup_service, function, AsyncMock(return_value={'status': 'ready'})) as call:
                for role in ROLES:
                    self.actor['role'] = role
                    response = self.request(f'/api/frontdesk/pickups/{endpoint}', 'POST')
                    self.assertEqual(response.code, 200 if role in ('frontdesk', 'admin') else 403)
                self.assertEqual(call.await_count, 2)

    def test_recharge_workflows_require_counter_role(self):
        from services import recharge_service
        cases = [('/api/frontdesk/recharge-customers?query=member', 'GET', recharge_service, 'find_customers'),
                 ('/api/frontdesk/recharges', 'GET', recharge_service, 'list_orders'),
                 ('/api/frontdesk/recharges', 'POST', recharge_service, 'create'),
                 ('/api/frontdesk/recharges/1', 'GET', recharge_service.repository, 'get'),
                 ('/api/frontdesk/recharges/1/cancel', 'POST', recharge_service, 'cancel')]
        for path, method, module, function in cases:
            with patch.object(module, function, AsyncMock(return_value={})) as call:
                for role in ROLES:
                    self.actor['role'] = role
                    response = self.request(path, method)
                    self.assertEqual(response.code, 200 if role in ('frontdesk', 'admin') else 403)
                self.assertEqual(call.await_count, 2)

    def test_maintenance_worklist_is_restricted_and_writes_are_unavailable(self):
        with patch.object(service, 'maintenance_blocks', AsyncMock(return_value={'items': []})) as call:
            for role in ROLES:
                self.actor['role'] = role
                self.assertEqual(self.request('/api/maintenance/court-blocks').code,200 if role in ('maintenance','admin') else 403)
            self.assertEqual(call.await_count,2)
            self.actor['role']='maintenance'
            self.assertEqual(self.request('/api/maintenance/court-blocks','POST').code,405)
            self.assertEqual(self.request('/api/frontdesk/court-slots').code,403)

    def test_database_role_and_status_are_reloaded_despite_admin_token_claim(self):
        self.actor['role']='admin'
        self.assertEqual(self.request('/probe').code,200)
        self.actor['role']='frontdesk'
        self.assertEqual(self.request('/probe').code,403)
        self.actor['role']='admin'; self.actor['status']=0
        self.assertEqual(self.request('/probe').code,403)
        self.assertEqual(self.get_user.await_count,3)

    def test_walkin_and_payment_endpoints_reject_customer_and_repair(self):
        paths = [('/api/frontdesk/walk-ins','GET'),('/api/frontdesk/walk-ins','POST'),
                 ('/api/frontdesk/walk-ins/quote','POST'),('/api/frontdesk/walk-ins/1','GET'),
                 ('/api/frontdesk/walk-ins/1/cancel','POST'),('/api/frontdesk/walk-ins/1/extensions','POST'),
                 ('/api/frontdesk/walk-ins/1/extensions/quote','POST'),('/api/payments/1','GET'),
                 ('/api/payments/1/mock-confirm','POST'),('/api/payments/1/mock-fail','POST')]
        for role in ('user','maintenance'):
            self.actor['role']=role
            for path,method in paths:
                if role=='user' and path.startswith('/api/payments/'): continue  # Own online payments are now supported.
                with self.subTest(role=role,path=path): self.assertEqual(self.request(path,method).code,403)


class StaffRulesTests(unittest.IsolatedAsyncioTestCase):
    async def test_public_register_rejects_privileged_role_before_any_write(self):
        for role in ('admin','frontdesk','maintenance','unknown'):
            with self.assertRaises(ApiError) as exc:
                await auth_service.register(None, {'role': role})
            self.assertEqual(exc.exception.status_code,400)

    async def test_maintenance_projection_and_boundary_states(self):
        now=datetime(2026,10,1,14,10)
        base={'id':1,'court_id':1,'court_no':'A1','court_name':'测试场','reserve_date':date(2026,10,1),
              'reason':'测试维修','block_type':'maintenance','status':'active','user_contact':'MUST NOT LEAK'}
        rows=[{**base,'start_time':time(15),'end_time':time(16)},
              {**base,'start_time':time(14),'end_time':time(15)},
              {**base,'start_time':time(13),'end_time':time(14,10)},
              {**base,'start_time':time(13),'end_time':time(16),'status':'released'}]
        with patch.object(service.operations,'list_blocks',AsyncMock(return_value=rows)) as fetch, patch.object(service,'datetime') as clock:
            clock.now.return_value=now
            result=await service.maintenance_blocks(None,'2026-10-01','2026-10-01',1,'in_progress')
        self.assertEqual([r['schedule_status'] for r in result['items']],['scheduled','in_progress','ended','released'])
        self.assertNotIn('user_contact',str(result))
        self.assertEqual(fetch.call_args.args[-2:],('maintenance','in_progress'))
        with self.assertRaises(ApiError): await service.maintenance_blocks(None,'2026-10-01','2026-10-01',schedule_status='bad')

    async def test_current_slot_remains_full_price_and_blocks_still_win(self):
        from services.config_service import ReservationRules
        now=datetime(2026,10,1,14,10)
        rules=SimpleNamespace(business_start_time=time(13),business_end_time=time(17),slot_interval_minutes=60,advance_reservation_days=7)
        court={'id':1,'status':1,'price_per_hour_cents':12000}
        with patch.object(court_service,'datetime') as clock, patch.object(court_service,'date') as dates, \
             patch.object(court_service.court_repository,'get_court_by_id',AsyncMock(return_value=court)), \
             patch.object(court_service.reservation_repository,'list_reservations_for_court_date',AsyncMock(return_value=[{'start_time':time(15),'end_time':time(16)}])), \
             patch.object(court_service.booking_operations_repository,'list_blocks',AsyncMock(return_value=[{'start_time':time(16),'end_time':time(17),'status':'active','reason':'维修'}])), \
             patch.object(court_service,'get_reservation_rules',AsyncMock(return_value=rules)), \
             patch.object(court_service,'locks_exist',AsyncMock(side_effect=lambda _,keys:[False]*len(keys))):
            clock.now.return_value=now; clock.combine.side_effect=datetime.combine; clock.strptime.side_effect=datetime.strptime
            dates.today.return_value=now.date()
            staff=await court_service.get_slots(None,court_id=1,date_arg='2026-10-01',refresh=False,allow_current=True)
            online=await court_service.get_slots(None,court_id=1,date_arg='2026-10-01',refresh=False)
        self.assertEqual([s['status'] for s in staff['slots']],['disabled','available','reserved','maintenance'])
        self.assertEqual(staff['slots'][1]['price_cents'],12000)
        self.assertEqual(online['slots'][1]['status'],'disabled')

if __name__ == '__main__': unittest.main()
