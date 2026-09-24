"""All-source administrator search and evidence on an owned disposable MySQL DB."""
import asyncio
from dataclasses import replace
from datetime import datetime
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
from repositories import database, admin_booking_repository as repo
from repositories.database import execute, fetch_all, close_pool
from services import reservation_service as service, staff_booking_service as staff, payment_service, booking_operations_service
from utils.response import ApiError


async def run():
    settings = replace(load_settings(), mysql_database='badminton_demo_admin_search_' + secrets.token_hex(8))
    name, created, checks = settings.mysql_database, False, []
    now = datetime(2026,10,1,14,10)
    con = await aiomysql.connect(host=settings.mysql_host,port=settings.mysql_port,user=settings.mysql_user,
        password=settings.mysql_password,autocommit=True)
    admin = {'id':1,'username':'admin_test','role':'admin'}
    user = {'id':2,'username':'customer_100%','role':'user'}
    desk = {'id':4,'username':'desk_one','role':'frontdesk'}
    key = lambda: secrets.token_hex(12)

    async def listing(**kwargs):
        args = {'status_arg':None,'page':1,'page_size':100,'offset':0,**kwargs}
        return await service.list_admin_reservations(settings,**args)

    async def ids(**kwargs):
        return {row['id'] for row in (await listing(**kwargs))['items']}

    async def expect_rejection(coro, code=400):
        try: await coro
        except ApiError as exc: assert exc.status_code == code, (exc.status_code,exc.message)
        else: raise AssertionError('Expected rejection')

    async def online(court=1, method='mock_alipay'):
        return await service.create_reservation(settings,current_user=user,body={
            'court_id':court,'reserve_date':'2026-10-02','start_time':'15:00','end_time':'16:00',
            'expected_amount_cents':10800,'pay_method':method,'request_key':key()})

    async def collect(pid, actor=user, action='mock_confirm'):
        return await payment_service.act(settings,actor,pid,action,{'request_key':key()})

    async def change(reservation,court,amount):
        return await booking_operations_service.reschedule(settings,reservation['id'],{
            'court_id':court,'reserve_date':'2026-10-02','start_time':'15:00','end_time':'16:00',
            'expected_amount_cents':amount,'expected_revision':reservation.get('revision',0),'request_key':key()},user)

    async def legacy(number='R-legacy-no-payment', uid=2):
        return await execute(settings,'''INSERT INTO reservation(reservation_no,user_id,court_id,reserve_date,
            start_time,end_time,time_slot,status,source,payable_amount_cents)
            VALUES (%s,%s,1,'2026-09-20','10:00','11:00','10:00-11:00','completed','online',12000)''',(number,uid))

    try:
        async with con.cursor() as cur:
            await cur.execute(f'CREATE DATABASE `{name}` CHARACTER SET utf8mb4'); created=True
            await cur.execute(f'USE `{name}`')
            for statement in re.findall(r'CREATE TABLE IF NOT EXISTS \w+ \(.*?\) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;', (ROOT/'sql/init.sql').read_text(),re.S):
                await cur.execute(statement)
        database._pool = await aiomysql.create_pool(host=settings.mysql_host,port=settings.mysql_port,
            user=settings.mysql_user,password=settings.mysql_password,db=name,minsize=1,maxsize=10,
            autocommit=True,init_command=f'SET timestamp={int(now.timestamp())}')
        await execute(settings,"""INSERT INTO user(id,username,password_hash,nickname,role,contact) VALUES
            (1,'admin_test','test','管理员','admin',NULL),(2,%s,'test','会员甲','user','13800138000'),
            (3,'customerX100Y','test','其他会员','user',NULL),(4,'desk_one','test','前台甲','frontdesk',NULL)""", (user['username'],))
        for uid in range(1,5):
            await execute(settings,"INSERT INTO member_account(user_id,member_level,balance_cents,points) VALUES (%s,'gold',100000,300)",(uid,))
        for cid,amount in enumerate([12000,12000,20000,12000,6000],1):
            await execute(settings,'INSERT INTO court(id,court_no,court_name,price_per_hour_cents) VALUES (%s,%s,%s,%s)',(cid,str(cid),'查询测试场'+str(cid),amount))

        first = await online()
        await collect(first['payment_id'],action='mock_fail')
        paid = await collect(first['payment_id'])
        # A later admin retry must not replace the first collecting member.
        await collect(first['payment_id'],admin)
        balance = await online(4,'balance'); await collect(balance['payment_id'],action='balance_pay')
        root = await staff.create(settings,desk,{'court_id':2,'reserve_date':'2026-10-01','start_time':'14:00',
            'end_time':'15:00','expected_amount_cents':12000,'guest_name':'散客_100%','guest_contact':'guest!contact', 'request_key':key()})
        await collect(root['payment']['id'],admin)
        canceled = await staff.create(settings,desk,{'end_time':'16:00','expected_amount_cents':12000,'request_key':key()},root['id'])
        await staff.action(settings,desk,canceled['id'],'cancel',{'request_key':key()})
        extension = await staff.create(settings,desk,{'end_time':'16:00','expected_amount_cents':12000,'request_key':key()},root['id'])
        await collect(extension['payment']['id'],desk)
        await staff.action(settings,admin,extension['id'],'refund',{'request_key':key(),'reason':'测试原渠道退回'})
        legacy_id = await legacy()
        other_legacy = await legacy('R-other-history',3)
        expected = {first['id'],balance['id'],root['id'],canceled['id'],extension['id'],legacy_id,other_legacy}

        assert await ids() == expected
        assert await ids(source_arg='walk_in') == {root['id']}
        assert await ids(source_arg='walk_in_extension') == {canceled['id'],extension['id']}
        assert await ids(source_arg='online') == {first['id'],balance['id'],legacy_id,other_legacy}
        assert await ids(pay_method_arg='balance') == {balance['id']}
        assert await ids(source_arg='walk_in_extension',pay_method_arg='mock_alipay',status_arg='canceled',court_id_arg='2',date_from_arg='2026-10-01',date_to_arg='2026-10-01') == {canceled['id'],extension['id']}
        assert await ids(username_arg='13800138000') == {first['id'],balance['id'],legacy_id}
        assert await ids(username_arg='guest!contact') == {root['id'],canceled['id'],extension['id']}
        assert await ids(username_arg='散客_100%') == {root['id'],canceled['id'],extension['id']}
        assert await ids(username_arg='%') == expected - {other_legacy}
        assert await ids(username_arg='customer_100%') == {first['id'],balance['id'],legacy_id}
        assert await ids(username_arg='不存在') == set()
        assert await ids(operator_arg='前台甲') == {root['id'],canceled['id'],extension['id']}
        assert await ids(operator_arg='admin_test') == set()  # Filter creator, not payment actor.
        assert await ids(operator_arg='desk_one') == {root['id'],canceled['id'],extension['id']}
        checks.append('all sources and legacy survive joins; combined date/court/status/channel/customer/creator filters work')

        first_page = await listing(page_size=2)
        pages = [await listing(page_size=2,page=number) for number in (1,2,3,4)]
        page_ids = [row['id'] for page in pages for row in page['items']]
        assert len(page_ids)==len(set(page_ids))==7 and set(page_ids)==expected
        assert all(page['total']==7 for page in pages)
        assert first_page['server_now']=='2026-10-01T14:10:00+08:00'
        assert not (await listing(page=99))['items']
        for invalid in ({'source_arg':'staff'},{'pay_method_arg':'cash'},{'status_arg':'paid'},
            {'operator_arg':'x'*51},{'username_arg':'x'*51},{'order_no_arg':'x'*65},
            {'court_id_arg':'0'},{'date_from_arg':'2026-10-02','date_to_arg':'2026-10-01'},
            {'page':0},{'page_size':101}):
            with patch.object(service,'refresh_reservation_statuses',AsyncMock()) as sweep:
                await expect_rejection(listing(**invalid)); sweep.assert_not_awaited()
        checks.append('stable pagination, inclusive dates, server clock and invalid filters rejected before status sweep')

        detail = await service.get_admin_reservation(settings,root['id'])
        assert {item['id'] for item in detail['chain']} == {root['id'],canceled['id'],extension['id']}
        assert detail['user_id'] is None and len(detail['payments'])==1 and detail['account_transactions']==[]
        p=detail['payments'][0]
        assert p['operator_id']==4 and p['collected_by']==1 and p['collector_username']=='admin_test'
        assert p['refunded_cents']==0
        ext_detail = await service.get_admin_reservation(settings,extension['id'])
        assert {item['id'] for item in ext_detail['chain']} == {root['id'],canceled['id'],extension['id']}
        assert len(ext_detail['refunds'])==1 and ext_detail['payments'][0]['refunded_cents']==12000
        assert ext_detail['refunds'][0]['operator_id']==1 and ext_detail['refunds'][0]['pay_method']=='mock_alipay'
        assert ext_detail['account_transactions']==[]
        for number in (extension['reservation_no'],ext_detail['order_no'],ext_detail['payments'][0]['payment_no'],ext_detail['refunds'][0]['refund_no']):
            assert await ids(order_no_arg=number)=={extension['id']}
        assert await ids(order_no_arg=extension['reservation_no'][:4]) == set()
        for word in ('request_hash','request_key','result_snapshot','context_snapshot','password_hash'):
            assert word not in json.dumps(detail,ensure_ascii=False)
        checks.append('complete root/extension chain includes cancellations; creators and first collectors distinct; exact related numbers, no internal credentials')

        supplement = await change(paid,3,18000)
        moved = await collect(supplement['payment']['id'])
        cheaper = await change(moved,5,5400)
        evidence = await service.get_admin_reservation(settings,first['id'])
        assert len(evidence['payments'])==2 and len(evidence['refunds'])==2 and len(evidence['changes'])==2
        assert evidence['payments'][0]['collected_by']==2 and evidence['payments'][1]['purpose']=='reschedule'
        assert [item['settlement_delta_cents'] for item in evidence['changes']]==[7200,-12600]
        assert sum(p['amount_cents']-p['refunded_cents'] for p in evidence['payments'])==5400
        assert evidence['changes'][0]['payment_order_id']==supplement['payment']['id']
        assert evidence['changes'][1]['refund_group_no']==evidence['refunds'][0]['refund_group_no']
        assert evidence['changes'][0]['before_snapshot']['court_name']=='查询测试场1'
        assert len(evidence['account_transactions'])>=2 and all(item['balance_change_cents']==0 for item in evidence['account_transactions'])
        assert await ids(order_no_arg=evidence['payments'][1]['payment_no'])=={first['id']}
        wallet = await service.get_admin_reservation(settings,balance['id'])
        assert wallet['account_transactions'][0]['balance_change_cents']==-10800
        historical = await service.get_admin_reservation(settings,legacy_id)
        assert historical['payments']==historical['refunds']==historical['account_transactions']==[]
        assert historical['attendance_outcome'] is None and historical['operator_name_snapshot'] is None
        await expect_rejection(service.get_admin_reservation(settings,999999),404)
        checks.append('supplements, split refunds, zero-wallet points and changes linked; missing legacy money/attendance never invented')

        # Inject a committed writer between count and page queries. One read snapshot
        # must keep the just-inserted record out of BOTH results until the next request.
        original_execute = aiomysql.DictCursor.execute
        inserted = []
        async def interleave(cursor,sql,args=None):
            result = await original_execute(cursor,sql,args)
            if sql.startswith('SELECT COUNT(*) AS total FROM reservation r') and not inserted:
                inserted.append(await legacy('R-concurrent-reader'))
            return result
        with patch.object(aiomysql.DictCursor,'execute',interleave):
            snapshot = await repo.list_page(settings,{},page=1,page_size=100)
        assert inserted and snapshot['total']==len(snapshot['items'])==7
        assert inserted[0] not in {item['id'] for item in snapshot['items']}
        assert (await listing())['total']==8
        checks.append('a concurrent committed insert cannot split list count and page; next request observes new state')
        print(json.dumps({'passed':len(checks),'checks':checks,'database_scope':'owned disposable database only'},ensure_ascii=False,indent=2))
    finally:
        await close_pool()
        if created:
            async with con.cursor() as cur: await cur.execute(f'DROP DATABASE `{name}`')
        con.close()

if __name__=='__main__': asyncio.run(run())
