#!/usr/bin/env python3
"""HTTP benchmark on an owned disposable database; no target-database argument."""
import asyncio
from dataclasses import replace
from datetime import date,datetime
import json
import logging
import math
from pathlib import Path
import platform
import re
import secrets
import sys
from time import perf_counter

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'backend'))
from dotenv import load_dotenv
load_dotenv(ROOT/'backend/.env')
import aiomysql
from tornado.httpclient import AsyncHTTPClient,HTTPRequest
from tornado.httpserver import HTTPServer
from tornado.netutil import bind_sockets
from tornado.web import Application
from config.settings import load_settings
from repositories import database
from repositories.database import close_pool,execute,fetch_one
from routes import build_routes
from services import shop_service
from utils.tokens import create_access_token

CONCURRENCY=20
SAMPLES=200


async def run():
    settings=replace(load_settings(),mysql_database='badminton_demo_perf_'+secrets.token_hex(8),jwt_secret=secrets.token_urlsafe(32),redis_db=14)
    name=settings.mysql_database;created=False;server=None;client=None
    con=await aiomysql.connect(host=settings.mysql_host,port=settings.mysql_port,user=settings.mysql_user,password=settings.mysql_password,autocommit=True)
    now=datetime.combine(date.today(),datetime.strptime('14:10','%H:%M').time())
    key=lambda:secrets.token_hex(12)
    try:
        async with con.cursor() as cur:
            await cur.execute(f'CREATE DATABASE `{name}` CHARACTER SET utf8mb4');created=True
            await cur.execute(f'USE `{name}`')
            for statement in re.findall(r'CREATE TABLE IF NOT EXISTS \w+ \(.*?\) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;', (ROOT/'sql/init.sql').read_text(),re.S):await cur.execute(statement)
            await cur.execute('SELECT VERSION()');mysql=(await cur.fetchone())[0]
        database._pool=await aiomysql.create_pool(host=settings.mysql_host,port=settings.mysql_port,user=settings.mysql_user,password=settings.mysql_password,db=name,minsize=1,maxsize=10,autocommit=True,init_command=f'SET timestamp={int(now.timestamp())}')
        actors=[{'id':1,'username':'perf_admin','role':'admin'}]+[{'id':i+2,'username':'perf_user_'+str(i),'role':'user'} for i in range(CONCURRENCY)]
        tokens={}
        for actor in actors:
            await execute(settings,"INSERT INTO user(id,username,password_hash,role) VALUES (%s,%s,'test-only',%s)",(actor['id'],actor['username'],actor['role']))
            await execute(settings,"INSERT INTO member_account(user_id,balance_cents,points) VALUES (%s,0,0)",(actor['id'],))
            tokens[actor['id']]=create_access_token(user_id=actor['id'],username=actor['username'],role=actor['role'],secret=settings.jwt_secret,expire_seconds=3600)
        await execute(settings,"INSERT INTO shop_product(id,product_no,product_name,price_cents,stock,status) VALUES (1,'PERF','隔离性能测试商品',1000,500,1)")
        body={'items':[{'product_id':1,'quantity':1,'expected_price_cents':1000}],'pay_method':'mock_alipay'}
        orders=[]
        for i in range(SAMPLES+1):
            actor=actors[1+i%CONCURRENCY]
            order=await shop_service.create_order(settings,current_user=actor,body={**body,'request_key':key()})
            orders.append((actor,order['payment_id']))
        server=HTTPServer(Application(build_routes(),app_settings=settings));sockets=bind_sockets(0,address='127.0.0.1');server.add_sockets(sockets)
        origin='http://127.0.0.1:'+str(sockets[0].getsockname()[1]);client=AsyncHTTPClient(force_instance=True,max_clients=CONCURRENCY)
        async def request(path,actor,body=None):
            response=await client.fetch(HTTPRequest(origin+path,method='POST' if body is not None else 'GET',
                headers={'Authorization':'Bearer '+tokens[actor['id']],'Content-Type':'application/json'},body=json.dumps(body) if body is not None else None,request_timeout=30),raise_error=False)
            payload=json.loads(response.body)
            assert response.code==200,(response.code,payload.get('message'))
            return payload['data']
        async def measure(label,work,limit):
            start=perf_counter();await work(0);cold=perf_counter()-start
            semaphore=asyncio.Semaphore(CONCURRENCY);elapsed=[];failures=[]
            async def sample(i):
                async with semaphore:
                    start=perf_counter()
                    try:await work(i+1)
                    except Exception as e:failures.append(type(e).__name__+': '+str(e))
                    finally:elapsed.append(perf_counter()-start)
            await asyncio.gather(*(sample(i) for i in range(SAMPLES)))
            elapsed.sort();p95=elapsed[math.ceil(.95*len(elapsed))-1]
            result={'name':label,'cold_ms':round(cold*1000,2),'warm_samples':SAMPLES,'concurrency':CONCURRENCY,
                'p50_ms':round(elapsed[len(elapsed)//2]*1000,2),'p95_ms':round(p95*1000,2),'max_ms':round(max(elapsed)*1000,2),'failures':len(failures),'target_ms':limit*1000,'passed':not failures and p95<=limit}
            assert not failures,failures[:3]
            return result
        async def quote(i):
            result=await request('/api/shop/orders/quote',actors[1+i%CONCURRENCY],body)
            assert result['total_amount_cents']==1000
        async def collect(i):
            actor,pid=orders[i];result=await request(f'/api/payments/{pid}/mock-confirm',actor,{'request_key':key()})
            assert result['status']=='paid' and result['payment_id']==pid and result['pickup_status']=='ready'
        async def listing(i):
            result=await request('/api/admin/transactions?date_from='+str(date.today())+'&date_to='+str(date.today()),actors[0])
            assert result['total']==SAMPLES+1 and result['summary']['channel_net_cents']==(SAMPLES+1)*1000
        results=[await measure('shop_quote',quote,2),await measure('mock_collection',collect,3),await measure('admin_financial_list',listing,2)]
        facts=await fetch_one(settings,"""SELECT (SELECT COUNT(*) FROM payment_order WHERE status='succeeded') AS payments,
            (SELECT COUNT(*) FROM shop_pickup WHERE status='ready') AS pickups,
            (SELECT stock FROM shop_product WHERE id=1) AS stock,(SELECT sold_count FROM shop_product WHERE id=1) AS sold,
            (SELECT COUNT(*) FROM member_account_transaction) AS wallet_effects,
            (SELECT COUNT(*) FROM shop_stock_hold WHERE status='active') AS active_holds""")
        assert facts=={'payments':201,'pickups':201,'stock':299,'sold':201,'wallet_effects':0,'active_holds':0},facts
        report={'executed_at':datetime.now().astimezone().isoformat(),'environment':{'os':platform.system(),'architecture':platform.machine(),'python':platform.python_version(),'mysql':mysql,'pool_max':10,'http':'loopback Tornado with normal JWT and role checks'},
            'scope':'owned disposable database; 20 customers, 1 product, 201 real pending orders, 201 distinct payments; no production capacity claim',
            'measurements':results,'final_facts':facts,'passed':all(item['passed'] for item in results)}
        print(json.dumps(report,ensure_ascii=False,indent=2))
        assert report['passed'],'Performance threshold missed; see measured report'
    finally:
        if client:client.close()
        if server:server.stop();await server.close_all_connections()
        await close_pool()
        if created:
            async with con.cursor() as cur:await cur.execute(f'DROP DATABASE `{name}`')
        con.close()

if __name__=='__main__':
    logging.getLogger('tornado.access').setLevel(logging.WARNING)
    asyncio.run(run())
