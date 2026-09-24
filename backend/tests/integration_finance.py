"""Unified financial evidence and accounting categories on an owned disposable database."""
import asyncio
from dataclasses import replace
from datetime import datetime,date
import json
from pathlib import Path
import re
import secrets
import sys
from unittest.mock import AsyncMock, patch
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'backend'))
from dotenv import load_dotenv
load_dotenv(ROOT/'backend/.env')
import aiomysql
from config.settings import load_settings
from repositories import database,finance_repository as repo,member_repository
from repositories.database import execute,fetch_all,fetch_one,close_pool
from services import finance_service as service,recharge_service,payment_service,shop_service,staff_booking_service,reservation_service,booking_operations_service
from utils.response import ApiError


async def run():
    s=replace(load_settings(),mysql_database='badminton_demo_finance_'+secrets.token_hex(8))
    name=s.mysql_database;created=False;checks=[];now=datetime(2026,10,1,14,10)
    con=await aiomysql.connect(host=s.mysql_host,port=s.mysql_port,user=s.mysql_user,password=s.mysql_password,autocommit=True)
    admin={'id':1,'username':'admin_test','role':'admin'};user={'id':2,'username':'member_100%','role':'user'};desk={'id':4,'username':'desk','role':'frontdesk'}
    key=lambda:secrets.token_hex(12)
    async def listing(**filters):return await service.list_transactions(s,{'date_from':'2026-10-01','date_to':'2026-10-02','page_size':'100',**filters})
    async def summary(**filters):return (await listing(**filters))['summary']
    async def collect(pid,actor=user,action='mock_confirm'):return await payment_service.act(s,actor,pid,action,{'request_key':key()})
    async def shop(method='balance',pid=1,price=10000):return await shop_service.create_order(s,current_user=user,body={
        'items':[{'product_id':pid,'quantity':1,'expected_price_cents':price}],'pay_method':method,'request_key':key()})
    async def refund(order):return await shop_service.admin_cancel_order(s,current_user=admin,order_id=order['id'],body={'request_key':key()})
    async def reject(coro,code=400):
        try:await coro
        except ApiError as e:assert e.status_code==code,(e.status_code,e.message)
        else:raise AssertionError('Expected rejection')
    try:
        async with con.cursor() as cur:
            await cur.execute(f'CREATE DATABASE `{name}` CHARACTER SET utf8mb4');created=True
            await cur.execute(f'USE `{name}`')
            for stmt in re.findall(r'CREATE TABLE IF NOT EXISTS \w+ \(.*?\) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;', (ROOT/'sql/init.sql').read_text(),re.S):await cur.execute(stmt)
        database._pool=await aiomysql.create_pool(host=s.mysql_host,port=s.mysql_port,user=s.mysql_user,password=s.mysql_password,
            db=name,minsize=1,maxsize=10,autocommit=True,init_command=f'SET timestamp={int(now.timestamp())}')
        await execute(s,"INSERT INTO user(id,username,password_hash,nickname,contact,role) VALUES (1,'admin_test','unused','管理员',NULL,'admin'),(2,%s,'unused','会员甲','13800138000','user'),(3,'memberX100Y','unused','其他会员',NULL,'user'),(4,'desk','unused','前台甲',NULL,'frontdesk')",(user['username'],))
        for uid in range(1,5):await execute(s,"INSERT INTO member_account(user_id,member_level,balance_cents,points) VALUES (%s,'normal',0,0)",(uid,))
        for pid,price in ((1,10000),(2,5000)):
            await execute(s,"INSERT INTO shop_product(id,product_no,product_name,price_cents,stock,status) VALUES (%s,%s,%s,%s,50,1)",(pid,'P'+str(pid),'财务测试商品'+str(pid),price))
        for cid,amount in ((1,12000),(2,10000),(3,18000),(4,6000)):
            await execute(s,'INSERT INTO court(id,court_no,court_name,price_per_hour_cents) VALUES (%s,%s,%s,%s)',(cid,str(cid),'财务测试场'+str(cid),amount))
        empty=await listing();assert empty['total']==0 and all(value==0 for value in empty['summary'].values())

        recharge=await recharge_service.create(s,desk,{'user_id':2,'amount_cents':10000,'request_key':key()})
        await collect(recharge['payment_id'],desk);await collect(recharge['payment_id'],admin)
        order=await shop();await collect(order['payment_id'],action='balance_pay')
        both=await listing();sums=both['summary']
        assert both['total']==2 and {r['record_type'] for r in both['items']}=={'payment'}
        assert sums['channel_receipts_cents']==sums['recharge_cents']==sums['balance_consumption_cents']==sums['consumption_net_cents']==10000
        assert sums['channel_net_cents']==10000 and sums['channel_refunds_cents']==0
        await refund(order)
        after=await summary();assert after['channel_net_cents']==10000 and after['balance_refunds_cents']==10000 and after['consumption_net_cents']==0
        assert (await fetch_one(s,'SELECT balance_cents FROM member_account WHERE user_id=2'))['balance_cents']==10000
        record=await service.detail(s,'payment',recharge['payment_id'])
        assert record['record']['operator_id']==4 and record['record']['created_by']==4 and len(record['account_transactions'])==1
        shop_detail=await service.detail(s,'payment',order['payment_id'])
        assert len(shop_detail['items'])==1 and shop_detail['items'][0]['product_name']=='财务测试商品1'
        assert len(shop_detail['account_transactions'])==2 and len(shop_detail['refunds'])==1
        checks.append('recharge 100 then balance consumption 100 reports channel 100, not 200; wallet refund distinct, no duplicated effects')

        mock=await shop('mock_alipay',2,5000);await collect(mock['payment_id']);await refund(mock)
        pending=await shop('mock_alipay',2,5000);await collect(pending['payment_id'],action='mock_fail')
        canceled=await shop('mock_alipay',2,5000)
        await shop_service.cancel_my_order(s,current_user=user,order_id=canceled['id'],body={'request_key':key()})
        await execute(s,"UPDATE payment_refund SET refunded_at='2026-10-02 10:00:00'")
        firstday=await summary(date_to='2026-10-01');secondday=await summary(date_from='2026-10-02')
        assert firstday['channel_receipts_cents']==15000 and firstday['channel_refunds_cents']==0 and firstday['consumption_net_cents']==15000
        assert secondday['channel_refunds_cents']==5000 and secondday['balance_refunds_cents']==10000 and secondday['consumption_net_cents']==-15000
        assert (await summary())['channel_net_cents']==10000
        assert len((await listing(status='pending'))['items'])==1 and all(v==0 for v in (await summary(status='pending')).values())
        assert len((await listing(status='canceled'))['items'])==1
        assert (await listing(order_no=mock['order_no']))['total']==2
        checks.append('paid facts retained after refund; actual money dates cross days correctly; pending/failure/cancel never enter money totals')

        root=await staff_booking_service.create(s,desk,{'court_id':1,'reserve_date':'2026-10-01','start_time':'14:00','end_time':'15:00','expected_amount_cents':12000,'guest_name':'散客甲','guest_contact':'guest-only','request_key':key()})
        await collect(root['payment']['id'],admin)
        ext=await staff_booking_service.create(s,desk,{'end_time':'16:00','expected_amount_cents':12000,'request_key':key()},root['id']);await collect(ext['payment']['id'],desk)
        body={'court_id':2,'reserve_date':'2026-10-02','start_time':'15:00','end_time':'16:00','expected_amount_cents':10000,'pay_method':'mock_alipay','request_key':key()}
        booking=await reservation_service.create_reservation(s,current_user=user,body=body);paid=await collect(booking['payment_id'])
        supplement=await booking_operations_service.reschedule(s,booking['id'],{**body,'court_id':3,'expected_amount_cents':18000,'expected_revision':paid['revision'],'request_key':key()},user)
        moved=await collect(supplement['payment']['id'])
        await booking_operations_service.reschedule(s,booking['id'],{**body,'court_id':4,'expected_amount_cents':6000,'expected_revision':moved['revision'],'request_key':key()},user)
        changes=await listing(business_type='reschedule');assert changes['summary']['consumption_receipts_cents']==8000 and changes['summary']['consumption_refunds_cents']==12000
        trace=await service.detail(s,'payment',booking['payment_id']);assert len(trace['changes'])==2 and len(trace['payments'])==2 and len(trace['refunds'])==2
        assert len((await listing(customer='guest-only'))['items'])==2
        actual=await listing(business_type='walk_in',operator='admin_test');assert actual['total']==1 and actual['items'][0]['created_by']==4 and actual['items'][0]['operator_id']==1
        assert (await listing(business_type='walk_in',operator='desk'))['total']==0
        assert (await listing(customer='member_100%'))['total']>0 and (await listing(customer='memberX100Y'))['total']==0
        recon=await repo.booking_reconciliation(s,date(2026,10,1),date(2026,10,2));assert recon=={'orders':3,'mismatches':0,'unverified':0},recon
        checks.append('guest and extension revenue, creator versus actual collector, supplements and split refunds, dual-channel booking reconciliation')

        account=await fetch_one(s,'SELECT * FROM member_account WHERE user_id=2')
        await member_repository.adjust_member_account_atomic(s,user_id=2,member_level='normal',expires_at=None,balance_change_cents=300,points_change=0,reason='测试调增',operator_id=1,operator_username='admin_test')
        await member_repository.adjust_member_account_atomic(s,user_id=2,member_level='normal',expires_at=None,balance_change_cents=-100,points_change=0,reason='测试调减',operator_id=1,operator_username='admin_test')
        adjustment=await listing(business_type='adjustment');assert adjustment['total']==2
        assert adjustment['summary']['adjustment_increase_cents']==300 and adjustment['summary']['adjustment_decrease_cents']==100
        assert adjustment['summary']['channel_receipts_cents']==adjustment['summary']['consumption_net_cents']==0
        legacy_rid=await execute(s,"INSERT INTO reservation(reservation_no,user_id,court_id,reserve_date,start_time,end_time,time_slot,status,payable_amount_cents) VALUES ('R-known-ledger',2,2,'2026-10-01','10:00','11:00','10:00-11:00','completed',300)")
        await execute(s,"INSERT INTO reservation_order(order_no,reservation_id,user_id,status,amount_cents,pay_method,expires_at,paid_at) VALUES ('RO-known-ledger',%s,2,'paid',300,'balance','2026-10-01 09:30','2026-10-01 09:00')",(legacy_rid,))
        before=await fetch_one(s,'SELECT balance_cents,points FROM member_account WHERE user_id=2')
        await execute(s,"INSERT INTO member_account_transaction(user_id,reservation_id,transaction_type,balance_change_cents,balance_before_cents,balance_after_cents,points_before,points_after,operator_id,operator_username,reason) VALUES (2,%s,'reservation_charge',-300,%s,%s,%s,%s,2,%s,'旧余额支付')",(legacy_rid,before['balance_cents'],before['balance_cents']-300,before['points'],before['points'],user['username']))
        await execute(s,'UPDATE member_account SET balance_cents=balance_cents-300 WHERE user_id=2')
        legacy_sid=await execute(s,"INSERT INTO shop_order(order_no,user_id,status,total_amount_cents,paid_at) VALUES ('SO-unverified',3,'paid',700,'2026-10-01 09:00')")
        legacy_rows=await listing(order_no='RO-known-ledger');assert legacy_rows['total']==1 and legacy_rows['items'][0]['record_type']=='account' and legacy_rows['summary']['balance_consumption_cents']==300
        unknown=await listing(order_no='SO-unverified');assert unknown['total']==1 and unknown['items'][0]['status']=='unverified' and unknown['summary']['consumption_receipts_cents']==0
        assert (await service.detail(s,'legacy_shop',legacy_sid))['account_transactions']==[]
        checks.append('manual adjustments isolated from income; known legacy wallet entries preserved once, unknown historical orders excluded from confirmed totals')

        assert (await listing())['reconciliation']['mismatches']==0
        await execute(s,'UPDATE member_account SET balance_cents=balance_cents+1 WHERE user_id=2')
        mismatch=await listing();assert mismatch['reconciliation']['mismatches']==1 and mismatch['reconciliation']['issues'][0]['user_id']==2
        await execute(s,'UPDATE member_account SET balance_cents=balance_cents-1 WHERE user_id=2')
        first_ledger=(await fetch_one(s,'SELECT MIN(id) AS id FROM member_account_transaction WHERE user_id=2'))['id']
        await execute(s,'UPDATE member_account_transaction SET balance_before_cents=balance_before_cents+1 WHERE id=%s',(first_ledger,))
        assert (await listing(entry_type='adjustment'))['reconciliation']['issues'][0]['chain_mismatch']==1
        await execute(s,'UPDATE member_account_transaction SET balance_before_cents=balance_before_cents-1 WHERE id=%s',(first_ledger,))
        assert (await listing())['reconciliation']['mismatches']==0
        checks.append('filtered customers reconcile full wallet history: ending balance and an earlier broken ledger link are both detected')

        all_rows=await listing();pages=[await listing(page=n,page_size=3) for n in range(1,(all_rows['total']+2)//3+1)]
        identities=[(row['record_type'],row['record_id']) for page in pages for row in page['items']]
        assert len(identities)==len(set(identities))==all_rows['total']
        assert all(page['summary']==all_rows['summary'] for page in pages)
        for row in all_rows['items']:
            d=await service.detail(s,row['record_type'],row['record_id'])
            assert (d['record']['record_type'],d['record']['record_id'])==(row['record_type'],row['record_id'])
            for field in ('password_hash','request_hash','request_key','context_snapshot','result_snapshot','redeem_request','code_svg'):
                assert field not in json.dumps(d,ensure_ascii=False)
        for invalid in ({'date_from':'2026-10-03'},{'date_from':'2025-01-01'}, {'business_type':'unknown'},{'entry_type':'cash'},{'pay_method':'alipay'},
            {'status':'paid'},{'customer':'x'*51},{'operator':'x'*51},{'order_no':'x'*65},{'page':'-1'},{'page_size':'101'}):
            with patch.object(service,'refresh_reservation_statuses',AsyncMock()) as refresh:
                await reject(listing(**invalid));refresh.assert_not_awaited()
        await reject(service.detail(s,'arbitrary_table',1));await reject(service.detail(s,'payment',999999),404)
        checks.append('all-source detail contract, page-independent aggregates, stable typed identities, empty ranges and strict filters')
        # A writer commits after SUM/COUNT and before wallet checks/page retrieval.
        # The response must preserve the pre-write aggregate, cohort and rows.
        original_execute=aiomysql.DictCursor.execute;injected=[]
        async def interleave(cursor,sql,args=None):
            value=await original_execute(cursor,sql,args)
            if sql.startswith('SELECT COUNT(*) AS total,') and not injected:
                injected.append(True)
                await member_repository.adjust_member_account_atomic(s,user_id=2,member_level='normal',expires_at=None,
                    balance_change_cents=100,points_change=0,reason='并发分页验收',operator_id=1,operator_username='admin_test')
            return value
        with patch.object(aiomysql.DictCursor,'execute',interleave):snapshot=await listing()
        assert snapshot['total']==all_rows['total']==len(snapshot['items'])
        assert snapshot['summary']==all_rows['summary'] and snapshot['reconciliation']['mismatches']==0
        newest=await listing();assert newest['total']==all_rows['total']+1
        assert newest['summary']['adjustment_increase_cents']==all_rows['summary']['adjustment_increase_cents']+100
        checks.append('concurrent adjustment between aggregate and page cannot split financial totals, wallet checks and visible rows')

        await execute(s,"INSERT INTO member_account_transaction(user_id,shop_order_id,transaction_type,balance_change_cents,balance_before_cents,balance_after_cents,reason) VALUES (3,%s,'shop_refund',500,0,500,'缺少原扣款的历史退款')",(legacy_sid,))
        orphan=await listing(order_no='SO-unverified')
        assert orphan['summary']['unverified_count']==2 and orphan['summary']['balance_refunds_cents']==0
        assert orphan['reconciliation']['mismatches']==1
        checks.append('legacy refund without original charge is marked for review, excluded from confirmed refunds and exposes wallet mismatch')
        print(json.dumps({'passed':len(checks),'checks':checks,'database_scope':'owned disposable database only'},ensure_ascii=False,indent=2))
    finally:
        await close_pool()
        if created:
            async with con.cursor() as cur:await cur.execute(f'DROP DATABASE `{name}`')
        con.close()
if __name__=='__main__':asyncio.run(run())
