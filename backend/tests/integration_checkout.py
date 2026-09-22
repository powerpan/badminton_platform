"""Price-agreement regression using a fresh demo database; removed on completion."""
import asyncio
from dataclasses import replace
from datetime import date, datetime, timedelta, time
import importlib.util
from pathlib import Path
import secrets
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
from dotenv import load_dotenv
load_dotenv(ROOT/'backend/.env')
from config.settings import load_settings
from repositories.database import execute, fetch_one, fetch_all, get_pool, close_pool
from services import shop_service
from repositories import reservation_repository
from utils.response import ApiError

async def run():
    spec=importlib.util.spec_from_file_location('demo',ROOT/'scripts/create_demo.py')
    demo=importlib.util.module_from_spec(spec);spec.loader.exec_module(demo)
    name='badminton_demo_checkout_'+datetime.now().strftime('%Y%m%d%H%M%S')+'_'+secrets.token_hex(3)
    await demo.create_demo(name,secrets.token_urlsafe(24),date.today(),datetime.now())
    settings=replace(load_settings(),mysql_database=name)
    actor={'id':2,'username':'demo_player','role':'user'}
    async def snapshot():
        return [await fetch_all(settings,q) for q in ['SELECT * FROM member_account WHERE user_id=2','SELECT * FROM shop_product ORDER BY id','SELECT * FROM shop_order','SELECT * FROM shop_order_item','SELECT * FROM member_account_transaction WHERE user_id=2']]
    async def reject(awaitable, expected_status=409):
        try: await awaitable
        except ApiError as e: assert e.status_code==expected_status,(e.status_code,e.message)
        else: raise AssertionError('Stale confirmed price was accepted and charged; expected rejection before any writes')
    try:
        await execute(settings,'UPDATE shop_product SET price_cents=1000,stock=10,status=1 WHERE id=1')
        body={'items':[{'product_id':1,'quantity':1,'expected_price_cents':1000}]}
        await execute(settings,'UPDATE shop_product SET price_cents=1500 WHERE id=1')
        before=await snapshot();await reject(shop_service.create_order(settings,current_user=actor,body=body));assert before==await snapshot()
        print('PASS: price changed after confirmation -> no order, stock change or debit')

        # A stale quote must fail on decreases as well, and each line is checked even if totals match.
        await execute(settings,'UPDATE shop_product SET price_cents=800 WHERE id=1')
        before=await snapshot();await reject(shop_service.create_order(settings,current_user=actor,body=body));assert before==await snapshot()
        await execute(settings,'UPDATE shop_product SET price_cents=1500 WHERE id=1')
        await execute(settings,'UPDATE shop_product SET price_cents=500,stock=10,status=1 WHERE id=2')
        swapped={'items':[{'product_id':i,'quantity':1,'expected_price_cents':1000} for i in [1,2]]}
        before=await snapshot();await reject(shop_service.create_order(settings,current_user=actor,body=swapped));assert before==await snapshot()
        print('PASS: decrease and offsetting line prices both require reconfirmation')
        q=await shop_service.quote_order(settings,current_user=actor,body=body)
        assert q['total_amount_cents']==1500 and q['can_checkout']
        fresh={'items':[{'product_id':1,'quantity':1,'expected_price_cents':1500}]}
        for column,value in [('stock',0),('status',0)]:
            await execute(settings,f'UPDATE shop_product SET {column}=%s WHERE id=1',(value,))
            q=await shop_service.quote_order(settings,current_user=actor,body=fresh);assert not q['can_checkout']
            before=await snapshot();await reject(shop_service.create_order(settings,current_user=actor,body=fresh),400);assert before==await snapshot()
            await execute(settings,'UPDATE shop_product SET stock=10,status=1 WHERE id=1')
        print('PASS: stock changes and delisting are reflected and enforced')
        saved=(await fetch_one(settings,'SELECT balance_cents FROM member_account WHERE user_id=2'))['balance_cents']
        for amount,status in [(500,400),(13000,409)]:
            # Demo has one unexpired pending reservation holding 12000 cents.
            await execute(settings,'UPDATE member_account SET balance_cents=%s WHERE user_id=2',(amount,))
            q=await shop_service.quote_order(settings,current_user=actor,body=fresh);assert not q['can_checkout']
            before=await snapshot();await reject(shop_service.create_order(settings,current_user=actor,body=fresh),status);assert before==await snapshot()
        await execute(settings,'UPDATE member_account SET balance_cents=%s WHERE user_id=2',(saved,))
        order=await shop_service.create_order(settings,current_user=actor,body=fresh)
        assert order['total_amount_cents']==1500
        assert (await fetch_one(settings,'SELECT balance_cents FROM member_account WHERE user_id=2'))['balance_cents']==saved-1500
        print('PASS: current/available balance enforced; freshly confirmed price charged exactly')
        before=await snapshot();await reject(shop_service.create_order(settings,current_user=actor,body={'items':[{'product_id':1,'quantity':1}]}),400);assert before==await snapshot()
        print('PASS: older clients cannot bypass price confirmation')
        # The authoritative booking transaction compares the UI's confirmed total before creating a hold.
        async def pending(expected):
            return await reservation_repository.create_pending_reservation_order_atomic(settings,
                reservation_no='PRICE-R',order_no='PRICE-O',user_id=2,court_id=1,reserve_date=date.today()+timedelta(days=2),
                start_time=time(9),end_time=time(10),time_slot='09:00-10:00',remark='',daily_limit=3,
                expires_at=datetime.now()+timedelta(minutes=10),expected_amount_cents=expected)
        await execute(settings,'UPDATE court SET price_per_hour_cents=15000 WHERE id=1')
        counts=await fetch_one(settings,'SELECT COUNT(*) AS n FROM reservation')
        assert (await pending(12000))[2]=='price_changed'
        assert counts==await fetch_one(settings,'SELECT COUNT(*) AS n FROM reservation')
        await execute(settings,"UPDATE member_account SET member_level='gold',expires_at=NULL WHERE user_id=2")
        assert (await pending(15000))[2]=='price_changed'
        created=await pending(13500);assert created[2] is None,created
        await execute(settings,'UPDATE court SET price_per_hour_cents=20000 WHERE id=1')
        paid=await reservation_repository.pay_reservation_order_atomic(settings,order_id=created[1],user_id=2,operator_username='demo_player')
        assert paid[1] is None,paid
        assert (await reservation_repository.get_reservation_detail(settings,created[0]))['payable_amount_cents']==13500
        print('PASS: booking court/member changes guarded; existing pending order keeps its agreed price')
    finally:
        pool=await get_pool(settings)
        async with pool.acquire() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute('SELECT project FROM demo_metadata');assert (await cursor.fetchone())[0]=='badminton_platform'
                assert name.startswith('badminton_demo_checkout_') and name!=load_settings().mysql_database
                await cursor.execute(f'DROP DATABASE `{name}`')
        await close_pool()

if __name__=='__main__':asyncio.run(run())
