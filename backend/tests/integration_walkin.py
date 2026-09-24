"""Walk-in money/concurrency checks on a disposable MySQL database and fixed DB clock."""
import asyncio
from dataclasses import replace
from datetime import datetime, time, timedelta
import json
from pathlib import Path
import re
import secrets
import sys
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
from dotenv import load_dotenv
load_dotenv(ROOT/'backend/.env')
import aiomysql
from config.settings import load_settings
from repositories import database, staff_booking_repository as repo, booking_operations_repository as ops, reservation_repository
from repositories.database import execute, fetch_all, fetch_one, close_pool
from services import staff_booking_service as service, reservation_service
from utils.response import ApiError


async def run():
    settings = load_settings()
    name = 'badminton_demo_walkin_' + secrets.token_hex(8)
    settings = replace(settings,mysql_database=name)
    con = await aiomysql.connect(host=settings.mysql_host,port=settings.mysql_port,user=settings.mysql_user,password=settings.mysql_password,autocommit=True)
    created = False
    checks = []
    now = datetime(2026,10,1,14,10)
    actor = {'id':3,'username':'desk_one','role':'frontdesk'}
    other = {'id':4,'username':'desk_two','role':'frontdesk'}
    admin = {'id':1,'username':'admin_test','role':'admin'}

    async def reject(coro, code=409):
        try: await coro
        except ApiError as exc: assert exc.status_code==code, (exc.status_code,exc.message)
        else: raise AssertionError('Expected rejection')

    async def money():
        return [await fetch_all(settings,'SELECT * FROM '+table+' ORDER BY '+key) for table,key in
                [('member_account','user_id'),('member_account_transaction','id')]]

    def payload(court=1, key=None):
        return {'court_id':court,'reserve_date':'2026-10-01','start_time':'14:00','end_time':'15:00',
                'expected_amount_cents':12000,'request_key':key or secrets.token_hex(12),'guest_name':'测试散客'}

    try:
        async with con.cursor() as cur:
            await cur.execute(f'CREATE DATABASE `{name}` CHARACTER SET utf8mb4'); created=True
            await cur.execute(f'USE `{name}`')
            for stmt in re.findall(r'CREATE TABLE IF NOT EXISTS \w+ \(.*?\) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;', (ROOT/'sql/init.sql').read_text(),re.S):
                await cur.execute(stmt)
        # Every pool connection sees 14:10, including SQL conflicts/expiration checks.
        database._pool = await aiomysql.create_pool(host=settings.mysql_host,port=settings.mysql_port,user=settings.mysql_user,
            password=settings.mysql_password,db=name,minsize=1,maxsize=10,autocommit=True,
            init_command=f'SET timestamp={int(now.timestamp())}')
        await execute(settings,"INSERT INTO user(id,username,password_hash,role) VALUES (1,'admin_test','test-only','admin'),(2,'customer','test-only','user'),(3,'desk_one','test-only','frontdesk'),(4,'desk_two','test-only','frontdesk'),(5,'repair','test-only','maintenance')")
        for uid in range(1,6):
            await execute(settings,'INSERT INTO member_account(user_id,balance_cents,points) VALUES (%s,88888,600)',(uid,))
        for cid in range(1,9):
            await execute(settings,'INSERT INTO court(id,court_no,court_name,price_per_hour_cents) VALUES (%s,%s,%s,12000)',(cid,'W'+str(cid),'隔离测试场'+str(cid)))
        untouched = await money()
        body = payload()
        quote = await service.quote(settings,actor,body)
        assert quote['payable_amount_cents']==12000 and quote['expires_at'].endswith('14:25:00+08:00')
        await execute(settings,'UPDATE court SET price_per_hour_cents=13000 WHERE id=1')
        await reject(service.create(settings,actor,body))
        assert not await fetch_all(settings,'SELECT id FROM reservation')
        await execute(settings,'UPDATE court SET price_per_hour_cents=12000 WHERE id=1')
        a,b = await asyncio.gather(service.create(settings,actor,body),service.create(settings,actor,body))
        assert a['id']==b['id'] and a['user_id'] is None and a['points_awarded']==0
        await reject(service.create(settings,actor,{**body,'guest_name':'另一位'}))
        checks.append('full current slot/original price, stale price refusal, create retry and mismatched key')

        failed = await service.action(settings,actor,a['id'],'mock_fail',{'request_key':'failure-once'})
        assert failed==await service.action(settings,actor,a['id'],'mock_fail',{'request_key':'failure-once'})
        await reject(service.action(settings,actor,a['id'],'mock_confirm',{'request_key':'failure-once'}))
        assert failed['payment']['status']=='pending'
        assert len(await fetch_all(settings,"SELECT id FROM operation_log WHERE action='mock_fail'"))==1
        with patch.object(repo,'audit',AsyncMock(side_effect=RuntimeError('injected audit fault'))):
            try: await service.action(settings,actor,a['id'],'mock_confirm',{'request_key':'fault-pay-001'})
            except RuntimeError: pass
            else: raise AssertionError('Fault not raised')
        assert (await repo.get_order(settings,a['id']))['payment']['status']=='pending'
        assert not await fetch_all(settings,"SELECT id FROM payment_command WHERE request_key='fault-pay-001'")
        p1,p2 = await asyncio.gather(service.action(settings,actor,a['id'],'mock_confirm',{'request_key':'pay-first-001'}),
                                   service.action(settings,other,a['id'],'mock_confirm',{'request_key':'pay-first-002'}))
        assert p1['status']==p2['status']=='confirmed'
        assert len(await fetch_all(settings,"SELECT id FROM operation_log WHERE action='mock_confirm'"))==1
        assert await money()==untouched
        checks.append('failed attempts and success retries, concurrent collection once, audit fault rolls back')

        extbody={'end_time':'16:00','expected_amount_cents':12000,'request_key':'extension-one'}
        ext = await service.create(settings,other,extbody,a['id'])
        assert ext['parent_reservation_id']==a['id'] and ext['root_reservation_id']==a['id']
        assert ext['guest_name']==a['guest_name'] and ext['start_time']=='15:00'
        await reject(service.action(settings,actor,a['id'],'cancel',{'request_key':'paid-cancel-test'}))
        await reject(reservation_service.admin_cancel_reservation(settings,a['id'],current_user=admin))
        await service.action(settings,actor,ext['id'],'cancel',{'request_key':'cancel-ext-001'})
        assert (await repo.get_order(settings,a['id']))['status']=='confirmed'
        ext2 = await service.create(settings,actor,{**extbody,'request_key':'extension-two'},a['id'])
        await service.action(settings,actor,ext2['id'],'mock_confirm',{'request_key':'pay-ext-two'})
        assert (await repo.get_order(settings,ext2['id']))['opened_at'] is None
        # Explicit administrator refund of extensions first prevents orphaned chains.
        await reservation_service.admin_cancel_reservation(settings,ext2['id'],current_user=admin)
        refunded = await reservation_service.admin_cancel_reservation(settings,a['id'],current_user=admin)
        repeat = await reservation_service.admin_cancel_reservation(settings,a['id'],current_user=admin)
        assert refunded['payment']['status']==repeat['payment']['status']=='refunded'
        assert len(await fetch_all(settings,'SELECT id FROM payment_refund'))==2 and await money()==untouched
        checks.append('adjacent linked extension, cancel leaves original, frontdesk cannot refund, original-channel refund once')

        contenders = await asyncio.gather(service.create(settings,actor,payload(2)),service.create(settings,other,payload(2)),return_exceptions=True)
        assert sum(isinstance(x,dict) for x in contenders)==1
        assert any(isinstance(x,ApiError) and x.status_code==409 for x in contenders)
        block_target={'court_id':3,'reserve_date':now.date(),'start_time':'14:00','end_time':'15:00'}
        contenders = await asyncio.gather(service.create(settings,actor,payload(3)),ops.create_block(settings,block_target,'隔离维护',admin),return_exceptions=True)
        assert sum(isinstance(x,ApiError) and x.status_code==409 for x in contenders)==1
        checks.append('two frontdesks and maintenance compete under the same court lock')

        stale = await service.create(settings,actor,payload(4))
        await execute(settings,'UPDATE payment_order SET expires_at=NOW()-INTERVAL 1 SECOND WHERE id=%s',(stale['payment']['id'],))
        await reject(service.action(settings,actor,stale['id'],'mock_confirm',{'request_key':'too-late-pay'}))
        result = await repo.get_order(settings,stale['id'])
        assert result['status']==result['order_status']==result['payment']['status']=='expired'
        assert (await service.create(settings,other,payload(4)))['id']!=stale['id']
        pending = await service.create(settings,actor,payload(5))
        await execute(settings,'UPDATE reservation_order SET expires_at=NOW()-INTERVAL 1 SECOND WHERE id=%s',(pending['order_id'],))
        await reservation_service.refresh_reservation_statuses(settings)
        assert (await repo.get_order(settings,pending['id']))['payment']['status']=='expired'
        checks.append('late success rejected; payment/order/reservation expire together and court is reusable')

        for role,uid in [('user',2),('maintenance',5)]:
            await reject(service.create(settings,{'id':uid,'role':role},payload(6)),403)
        await execute(settings,"UPDATE user SET role='maintenance' WHERE id=4")
        await reject(service.create(settings,other,payload(6)),403)
        assert await money()==untouched
        page = await service.list_orders(settings,{'date':'2026-10-01','page_size':2})
        assert len(page['items'])==2 and page['total']>2
        assert (await reservation_service.get_admin_reservation(settings,a['id']))['source']=='walk_in'
        checks.append('roles rechecked in transaction; admin sees guests; pagination and all wallet balances conserved')
        await execute(settings,'UPDATE court SET price_per_hour_cents=0 WHERE id=7')
        free = await service.create(settings,actor,{**payload(7),'expected_amount_cents':0})
        await service.action(settings,actor,free['id'],'mock_confirm',{'request_key':'free-confirm-test'})
        await reservation_service.admin_cancel_reservation(settings,free['id'],current_user=admin)
        assert len(await fetch_all(settings,'SELECT id FROM payment_refund'))==2
        checks.append('zero-priced court cancels without fabricating a zero-value refund')
        root = await service.create(settings,actor,payload(8))
        await service.action(settings,actor,root['id'],'mock_confirm',{'request_key':'race-root-pay'})
        online,extension = await asyncio.gather(
            reservation_repository.create_pending_reservation_order_atomic(settings,
                reservation_no='ONLINE-RACE',order_no='ONLINE-ORDER-RACE',user_id=2,court_id=8,
                reserve_date=now.date(),start_time=time(15),end_time=time(16),time_slot='15:00-16:00',
                remark='',daily_limit=3,expires_at=now+timedelta(minutes=15),expected_amount_cents=12000),
            service.create(settings,actor,{'end_time':'16:00','expected_amount_cents':12000,'request_key':'race-extension'},root['id']),
            return_exceptions=True)
        successes = int(isinstance(online,tuple) and online[2] is None)+int(isinstance(extension,dict))
        assert successes==1,(online,extension)
        assert len(await fetch_all(settings,"SELECT id FROM reservation WHERE court_id=8 AND start_time='15:00' AND status='pending'"))==1
        assert await money()==untouched
        checks.append('existing online checkout and staff extension race: exactly one adjacent occupancy')
        print(json.dumps({'passed':True,'checks':checks,'database_scope':'disposable only'},ensure_ascii=False,indent=2))
    finally:
        await close_pool()
        if created:
            async with con.cursor() as cur: await cur.execute(f'DROP DATABASE `{name}`')
        con.close()


if __name__=='__main__': asyncio.run(run())
