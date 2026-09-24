"""Explicit integration runner. Creates its own isolated database; never uses business data.

From repository root: backend/.venv/bin/python backend/tests/integration_operations.py
Pass --keep to inspect the newly created database; otherwise only that new database is removed.
"""
import argparse
import asyncio
from dataclasses import replace
from datetime import date, datetime, time, timedelta
import importlib.util
import json
from pathlib import Path
import secrets
import sys
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
from dotenv import load_dotenv
load_dotenv(ROOT/'backend/.env')
from config.settings import load_settings
from repositories import booking_operations_repository as ops, reservation_repository as reservations
from repositories.database import fetch_one, fetch_all, execute, close_pool, get_pool
from services import booking_operations_service as service
from services.operations_statistics_service import report
from utils.response import ApiError


async def run(keep=False):
    spec=importlib.util.spec_from_file_location('demo',ROOT/'scripts/create_demo.py')
    demo=importlib.util.module_from_spec(spec);spec.loader.exec_module(demo)
    name='badminton_demo_ops_'+datetime.now().strftime('%Y%m%d%H%M%S')+'_'+secrets.token_hex(3)
    await demo.create_demo(name,secrets.token_urlsafe(24),date.today(),datetime.now())
    print('Created isolated test database:',name,flush=True)
    with Path('/tmp/badminton-phase3-created-databases.txt').open('a') as record:
        record.write(name+'\n')
    settings=replace(load_settings(),mysql_database=name)
    actor={'id':2,'username':'demo_player','role':'user'}
    manager={'id':1,'username':'demo_manager','role':'admin'}
    tomorrow=date.today()+timedelta(days=1)
    checks=[]
    async def state(rid=1):
        return {'reservation':await reservations.get_reservation_detail(settings,rid),
                'account':await fetch_one(settings,'SELECT * FROM member_account WHERE user_id=2'),
                'history':await ops.change_history(settings,rid),
                'ledger':await fetch_all(settings,'SELECT * FROM member_account_transaction WHERE reservation_id=%s',(rid,)),
                'notifications':await fetch_all(settings,"SELECT * FROM notification WHERE user_id=2 AND title='预约改期成功'")}
    def target(court,hour,day=tomorrow,duration=1):
        return {'court_id':court,'reserve_date':str(day),'start_time':f'{hour:02}:00','end_time':f'{hour+duration:02}:00'}
    async def payload(rid,body):
        q=await service.quote(settings,rid,body,actor)
        return {**body,'expected_revision':q['revision'],'expected_amount_cents':q['payable_amount_cents'],'request_key':secrets.token_hex(16)}
    async def rejected(awaitable, text=None):
        try: await awaitable
        except ApiError as exc:
            if text: assert text in exc.message, exc.message
            return
        raise AssertionError('Expected rejection')
    try:
        await execute(settings,'UPDATE court SET price_per_hour_cents=CASE id WHEN 1 THEN 13000 WHEN 2 THEN 12000 ELSE 10000 END')
        # Upgrade an old schema twice; existing financial rows must survive unchanged.
        before=await state()
        for table in ('reservation_change','reservation_attendance','court_block'):
            await execute(settings,f'DROP TABLE `{table}`')
        spec=importlib.util.spec_from_file_location('migration',ROOT/'scripts/migrate_booking_operations.py')
        migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
        await migration.migrate(name,True);await migration.migrate(name,True)
        staff_spec=importlib.util.spec_from_file_location('staff_migration',ROOT/'scripts/migrate_staff_payments.py')
        staff_migration=importlib.util.module_from_spec(staff_spec);staff_spec.loader.exec_module(staff_migration)
        await staff_migration.migrate(name,True)
        assert before==await state();checks.append('old-schema migration, repeat, data preservation')
        p=await payload(1,target(1,10,duration=2))
        old=await state();await service.reschedule(settings,1,p,actor);new=await state()
        assert new['account']['balance_cents']-old['account']['balance_cents']==-14000
        assert new['reservation']['order_amount_cents']==new['reservation']['payable_amount_cents']==26000
        assert len(new['history'])==1 and len(new['notifications'])==1
        await service.reschedule(settings,1,p,actor);assert new==await state()
        await rejected(service.reschedule(settings,1,{**p,'start_time':'11:00','end_time':'13:00'},actor),'请求号')
        checks.append('higher price, ledger/order/notification, duplicate and reused key')
        p=await payload(1,target(3,12,day=tomorrow+timedelta(days=1)))
        await service.reschedule(settings,1,p,actor);after=await state()
        assert after['account']['balance_cents']-new['account']['balance_cents']==16000
        assert after['reservation']['points_awarded']==100
        checks.append('lower price refunds difference and adjusts points')
        stale=await payload(1,target(3,14,day=tomorrow+timedelta(days=1)))
        await service.reschedule(settings,1,stale,actor)
        await rejected(service.reschedule(settings,1,{**stale,'request_key':secrets.token_hex(16),'start_time':'15:00','end_time':'16:00'},actor),'已变化')
        checks.append('zero difference and stale revision')
        # Failure injected after monetary writes proves rollback covers the complete transaction.
        p=await payload(1,target(1,10,day=tomorrow+timedelta(days=2)))
        old=await state()
        with patch.object(ops,'audit',side_effect=RuntimeError('injected failure')):
            try: await service.reschedule(settings,1,p,actor)
            except RuntimeError: pass
            else: raise AssertionError('Fault not injected')
        assert old==await state();checks.append('fault after money/history/notification writes rolls back all')
        # Balance includes pending holds; restore the isolated account after the failed operation.
        saved=old['account']['balance_cents']
        await execute(settings,'UPDATE member_account SET balance_cents=12001 WHERE user_id=2')
        low=await state();await rejected(service.reschedule(settings,1,p,actor),'可用余额不足')
        assert low==await state()
        await execute(settings,'UPDATE member_account SET balance_cents=%s WHERE user_id=2',(saved,))
        checks.append('insufficient available balance keeps original')
        # Concurrent requests for the same reservation can commit only one revision.
        p1=await payload(1,target(1,10,day=tomorrow+timedelta(days=2)))
        p2={**p1,'start_time':'11:00','end_time':'12:00','request_key':secrets.token_hex(16)}
        results=await asyncio.gather(service.reschedule(settings,1,p1,actor),service.reschedule(settings,1,p2,actor),return_exceptions=True)
        assert sum(isinstance(x,dict) for x in results)==1,results
        assert sum(isinstance(x,ApiError) for x in results)==1,results
        checks.append('concurrent reschedules one commit')
        # Changed prices and incomplete payment evidence reject without touching the original.
        p=await payload(1,target(2,15,day=tomorrow+timedelta(days=2)))
        old=await state()
        await execute(settings,'UPDATE court SET price_per_hour_cents=12001 WHERE id=2')
        await rejected(service.reschedule(settings,1,p,actor),'价格')
        assert old==await state()
        await execute(settings,'UPDATE court SET price_per_hour_cents=12000 WHERE id=2')
        await execute(settings,"UPDATE member_account_transaction SET transaction_type='qa_unverified' WHERE reservation_id=1 AND transaction_type='reservation_charge'")
        unverified=await state()
        await rejected(service.reschedule(settings,1,p,actor),'流水')
        assert unverified==await state()
        await execute(settings,"UPDATE member_account_transaction SET transaction_type='reservation_charge' WHERE reservation_id=1 AND transaction_type='qa_unverified'")
        await rejected(service.quote(settings,1,target(2,15),{'id':3,'role':'user'}),'不存在')
        checks.append('changed price, unverified old payment, ownership rejection')
        # A fresh booking and reschedule for the same target cannot both win.
        move_day=tomorrow+timedelta(days=4)
        p=await payload(1,target(2,10,day=move_day))
        async def competing_booking():
            return await reservations.create_pending_reservation_order_atomic(settings,reservation_no='QA-MOVE-RACE',order_no='QA-MOVE-RACE-O',user_id=3,
                court_id=2,reserve_date=move_day,start_time=time(10),end_time=time(11),time_slot='10:00-11:00',remark='',daily_limit=3,expires_at=datetime.now()+timedelta(minutes=10))
        results=await asyncio.gather(service.reschedule(settings,1,p,actor),competing_booking(),return_exceptions=True)
        occupied=await fetch_one(settings,"SELECT COUNT(*) AS n FROM reservation WHERE court_id=2 AND reserve_date=%s AND start_time<'11:00' AND end_time>'10:00' AND status IN ('confirmed','pending')",(move_day,))
        assert occupied['n']==1,results
        checks.append('new booking versus reschedule concurrent exclusion')
        # A new order and a maintenance block race through the same court lock.
        day=tomorrow+timedelta(days=3)
        t={'court_id':3,'reserve_date':day,'start_time':time(9),'end_time':time(10)}
        async def pending():
            return await reservations.create_pending_reservation_order_atomic(settings,reservation_no='QA-RACE',order_no='QA-RACE-O',user_id=3,
                **t,time_slot='09:00-10:00',remark='',daily_limit=3,expires_at=datetime.now()+timedelta(minutes=10))
        result=await asyncio.gather(pending(),ops.create_block(settings,t,'隔离维护',manager),return_exceptions=True)
        booked=await fetch_one(settings,"SELECT COUNT(*) AS n FROM reservation WHERE reservation_no='QA-RACE'")
        blocked=await fetch_one(settings,"SELECT COUNT(*) AS n FROM court_block WHERE court_id=3 AND reserve_date=%s AND status='active'",(day,))
        assert booked['n']+blocked['n']==1,result
        checks.append('maintenance versus booking concurrent exclusion')
        # Exact adjacency allowed, overlap rejected, release idempotent and logged once.
        t={'court_id':2,'reserve_date':tomorrow,'start_time':time(17),'end_time':time(18)}
        block_id=await ops.create_block(settings,t,'隔离相邻维护',manager)
        await rejected(ops.create_block(settings,{**t,'end_time':time(18,30)},'隔离冲突',manager))
        await rejected(ops.create_block(settings,t,'重复维护',manager))
        await ops.release_block(settings,block_id,manager);await ops.release_block(settings,block_id,manager)
        count=await fetch_one(settings,"SELECT COUNT(*) AS n FROM operation_log WHERE action='release' AND target_id=%s",(block_id,));assert count['n']==1
        checks.append('adjacency, overlapping block, release idempotence')
        # Attendance uses reservation locks and never infers historic presence.
        # Keep the attendance fixture within one date and outside today's ended-session metrics.
        now=(datetime.now()+timedelta(days=1)).replace(hour=14,minute=10,second=0,microsecond=0)
        await execute(settings,"UPDATE reservation SET reserve_date=%s,start_time=%s,end_time=%s,status='confirmed' WHERE id=2",
            (now.date(),(now-timedelta(minutes=10)).time(),(now+timedelta(minutes=50)).time()))
        with patch('utils.booking_operations.datetime',wraps=datetime) as clock:
            clock.now.return_value=now
            await asyncio.gather(ops.record_attendance(settings,2,'checked_in',manager),ops.record_attendance(settings,2,'checked_in',manager))
        await rejected(ops.record_attendance(settings,2,'no_show',manager),'不同到场')
        canceled=await reservations.cancel_reservation_atomic(settings,2,operator_id=1,operator_username='demo_manager',reason='QA')
        assert canceled[1]=='attendance_recorded'
        historic=await fetch_one(settings,"SELECT id FROM reservation WHERE status='completed' LIMIT 1")
        await ops.record_attendance(settings,historic['id'],'no_show',manager)
        checks.append('attendance repeat/concurrent, conflicting outcome, cancel guard, no-show')
        data=await report(settings,str(date.today()-timedelta(days=60)),str(tomorrow+timedelta(days=5)))
        assert data['reconciliation']['mismatches']==0,data['reconciliation']
        assert data['unrecorded']>0 and data['attendance_rate']==0
        ledger=await fetch_one(settings,'SELECT SUM(balance_change_cents) AS b,SUM(points_change) AS p FROM member_account_transaction WHERE user_id=2')
        account=await fetch_one(settings,'SELECT balance_cents,points FROM member_account WHERE user_id=2')
        assert int(ledger['b'])==account['balance_cents'] and int(ledger['p'])==account['points']
        checks.append('dashboard order reconciliation and member ledger balance')
        print(json.dumps({'database':name,'passed':checks,'count':len(checks)},ensure_ascii=False,indent=2))
        if keep: Path('/tmp/badminton-phase3-integration-database.txt').write_text(name)
    finally:
        if not keep:
            pool=await get_pool(settings)
            async with pool.acquire() as c:
                async with c.cursor() as cursor:
                    await cursor.execute('SELECT project FROM demo_metadata')
                    assert (await cursor.fetchone())[0]=='badminton_platform'
                    assert name.startswith('badminton_demo_ops_') and name!=load_settings().mysql_database
                    await cursor.execute(f'DROP DATABASE `{name}`')
        await close_pool()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--keep',action='store_true')
    asyncio.run(run(parser.parse_args().keep))
