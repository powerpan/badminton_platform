"""Real HTTP response-loss and process-restart checks on an owned disposable DB."""
import asyncio
from dataclasses import asdict,replace
from datetime import date,datetime,timedelta
import json
from pathlib import Path
import re
import secrets
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'backend'))
from dotenv import load_dotenv
load_dotenv(ROOT/'backend/.env')
import aiomysql
from config.settings import Settings,load_settings
from repositories import database
from repositories.database import close_pool,execute,fetch_one
from tornado.httpclient import AsyncHTTPClient,HTTPRequest,HTTPClientError
from utils.tokens import create_access_token


async def serve(config_path):
    from handlers.base import BaseHandler
    from routes import build_routes
    from tornado.httpserver import HTTPServer
    from tornado.netutil import bind_sockets
    from tornado.web import Application
    config=Path(config_path);settings=Settings(**json.loads(config.read_text()));fault=config.parent/'fault.json'
    assert re.fullmatch('badminton_demo_delivery_[0-9a-f]{16}',settings.mysql_database)
    fixed=datetime.combine(date.today(),datetime.strptime('14:10','%H:%M').time())
    database._pool=await aiomysql.create_pool(host=settings.mysql_host,port=settings.mysql_port,user=settings.mysql_user,
        password=settings.mysql_password,db=settings.mysql_database,minsize=1,maxsize=10,autocommit=True,init_command=f'SET timestamp={int(fixed.timestamp())}')
    original=BaseHandler.write_json
    def write(self,payload,status_code=200):
        rules=json.loads(fault.read_text()) if fault.exists() else []
        for rule in rules:
            if status_code==200 and rule['remaining'] and self.request.path==rule['path'] and self.request.method==rule['method']:
                rule['remaining']-=1;fault.write_text(json.dumps(rules))
                if rule['effect']=='drop':self.request.connection.stream.close();return
                return original(self,{'code':503,'message':'测试：资料查询暂时失败'},503)
        return original(self,payload,status_code)
    BaseHandler.write_json=write
    sockets=bind_sockets(0,address='127.0.0.1');server=HTTPServer(Application(build_routes(),app_settings=settings));server.add_sockets(sockets)
    print(json.dumps({'port':sockets[0].getsockname()[1]}),flush=True)
    try:await asyncio.to_thread(sys.stdin.buffer.read,1)
    finally:server.stop();await server.close_all_connections();await close_pool()


async def run():
    settings=replace(load_settings(),mysql_database='badminton_demo_delivery_'+secrets.token_hex(8),jwt_secret=secrets.token_urlsafe(32),redis_db=14)
    con=await aiomysql.connect(host=settings.mysql_host,port=settings.mysql_port,user=settings.mysql_user,password=settings.mysql_password,autocommit=True)
    name=settings.mysql_database;created=False;process=None;client=AsyncHTTPClient(force_instance=True);checks=[];restarts=0
    actors={1:('test_admin','admin'),2:('test_customer','user'),3:('test_desk','frontdesk'),4:('test_repair','maintenance')}
    tokens={uid:create_access_token(user_id=uid,username=data[0],role=data[1],secret=settings.jwt_secret,expire_seconds=3600) for uid,data in actors.items()}
    key=lambda:secrets.token_hex(12)
    with tempfile.TemporaryDirectory(prefix='bf-delivery-') as temp:
        config=Path(temp)/'settings.json';config.touch(mode=0o600);config.write_text(json.dumps(asdict(settings)));fault=Path(temp)/'fault.json'
        async def stop():
            nonlocal process
            if process and process.returncode is None:
                process.stdin.write(b'q');await process.stdin.drain()
                try:await asyncio.wait_for(process.wait(),10)
                except asyncio.TimeoutError:process.kill();await process.wait();raise
            process=None
        async def start():
            nonlocal process,restarts,origin
            await stop()
            process=await asyncio.create_subprocess_exec(sys.executable,'-B',__file__,'--serve',str(config),stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL)
            line=await asyncio.wait_for(process.stdout.readline(),10);ready=json.loads(line);origin='http://127.0.0.1:'+str(ready['port']);restarts+=1
        def arm(path,method='POST',effect='drop'):
            fault.write_text(json.dumps([{'path':path,'method':method,'effect':effect,'remaining':1}]))
        async def request(path,body=None,uid=2,method=None,expected=200):
            try:
                response=await client.fetch(HTTPRequest(origin+path,method=method or ('POST' if body is not None else 'GET'),
                    headers={'Authorization':'Bearer '+tokens[uid],'Content-Type':'application/json'},
                    body=json.dumps(body) if body is not None else None,request_timeout=10),raise_error=False)
                status=response.code;data=json.loads(response.body)
            except HTTPClientError as e:
                status=e.code;data={}
            assert status==expected,(path,status,expected,data.get('message'))
            return data.get('data')
        async def counts():
            return await fetch_one(settings,"""SELECT (SELECT COUNT(*) FROM shop_order) AS orders,
                (SELECT COUNT(*) FROM payment_order) AS payments,(SELECT COUNT(*) FROM member_account_transaction) AS ledger,
                (SELECT COUNT(*) FROM shop_pickup) AS pickups,(SELECT stock FROM shop_product WHERE id=1) AS stock,
                (SELECT sold_count FROM shop_product WHERE id=1) AS sold,(SELECT balance_cents FROM member_account WHERE user_id=2) AS balance""")
        try:
            async with con.cursor() as cur:
                await cur.execute(f'CREATE DATABASE `{name}` CHARACTER SET utf8mb4');created=True;await cur.execute(f'USE `{name}`')
                for ddl in re.findall(r'CREATE TABLE IF NOT EXISTS \w+ \(.*?\) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;', (ROOT/'sql/init.sql').read_text(),re.S):await cur.execute(ddl)
            for uid,(username,role) in actors.items():
                await execute(settings,"INSERT INTO user(id,username,password_hash,role) VALUES (%s,%s,'test-only',%s)",(uid,username,role))
                await execute(settings,'INSERT INTO member_account(user_id,balance_cents,points) VALUES (%s,%s,0)',(uid,20000 if uid==2 else 0))
            await execute(settings,"INSERT INTO shop_product(id,product_no,product_name,price_cents,stock) VALUES (1,'D06','恢复测试商品',500,10)")
            await execute(settings,"INSERT INTO court(id,court_no,court_name,price_per_hour_cents) VALUES (1,'D06','恢复测试场地',10000)")
            origin='';await start()
            body={'items':[{'product_id':1,'quantity':1,'expected_price_cents':500}],'pay_method':'balance','request_key':key()}
            arm('/api/shop/orders');await request('/api/shop/orders',body,expected=599)
            assert (await counts())['orders']==1
            await start();order=await request('/api/shop/orders',body);assert (await counts())['orders']==1
            assert order['status']=='pending';pid=order['payment_id'];paybody={'request_key':key()}
            checks.append('committed creation with lost TCP response resumes the same shop order after a new backend process')

            arm(f'/api/payments/{pid}/balance-pay');await request(f'/api/payments/{pid}/balance-pay',paybody,expected=599)
            arm('/api/auth/profile','GET','error');await request('/api/auth/profile',expected=503)
            paid_facts=await counts();assert paid_facts=={'orders':1,'payments':1,'ledger':1,'pickups':1,'stock':9,'sold':1,'balance':19500},paid_facts
            await start()
            assert (await request(f'/api/payments/{pid}'))['status']=='succeeded'
            await request(f'/api/payments/{pid}/balance-pay',paybody)
            await request(f'/api/payments/{pid}/balance-pay',{'request_key':key()})
            assert await counts()==paid_facts
            assert (await request('/api/auth/profile'))['member']['balance_cents']==19500
            checks.append('lost paid response and separate profile failure cannot repeat wallet debit, stock or pickup after restart and retries')

            booking_body={'court_id':1,'reserve_date':str(date.today()+timedelta(days=2)),'start_time':'15:00','end_time':'16:00',
                'expected_amount_cents':10000,'pay_method':'mock_alipay','request_key':key()}
            arm('/api/reservations');await request('/api/reservations',booking_body,expected=599)
            booking=await request('/api/reservations',booking_body);pid=booking['payment_id'];paybody={'request_key':key()}
            arm(f'/api/payments/{pid}/mock-confirm');await request(f'/api/payments/{pid}/mock-confirm',paybody,expected=599)
            await start()
            assert (await request(f'/api/payments/{pid}'))['status']=='succeeded'
            await request(f'/api/payments/{pid}/mock-confirm',paybody)
            detail=await request('/api/reservations/'+str(booking['id']));assert detail['status']=='confirmed'
            assert (await counts())['balance']==19500
            assert (await fetch_one(settings,'SELECT COUNT(*) AS n FROM reservation'))['n']==1
            checks.append('online creation and simulated-payment response losses recover original booking across process restart without wallet debit')

            walk_body={'court_id':1,'reserve_date':str(date.today()),'start_time':'14:00','end_time':'15:00','expected_amount_cents':10000,'guest_name':'恢复验收散客','request_key':key()}
            arm('/api/frontdesk/walk-ins');await request('/api/frontdesk/walk-ins',walk_body,uid=3,expected=599)
            walk=await request('/api/frontdesk/walk-ins',walk_body,uid=3);pid=walk['payment']['id'];paybody={'request_key':key()}
            arm(f'/api/payments/{pid}/mock-confirm');await request(f'/api/payments/{pid}/mock-confirm',paybody,uid=3,expected=599)
            await start();await request(f'/api/payments/{pid}/mock-confirm',paybody,uid=3)
            assert (await request('/api/frontdesk/walk-ins/'+str(walk['id']),uid=3))['status']=='confirmed'
            assert (await fetch_one(settings,'SELECT COUNT(*) AS n FROM reservation'))['n']==2
            assert (await fetch_one(settings,'SELECT balance_cents,points FROM member_account WHERE user_id=3'))=={'balance_cents':0,'points':0}
            checks.append('counter walk-in creation and collection recover one guest booking after lost responses and backend restart')

            charge_body={'user_id':2,'amount_cents':10000,'request_key':key()}
            arm('/api/frontdesk/recharges');await request('/api/frontdesk/recharges',charge_body,uid=3,expected=599)
            charge=await request('/api/frontdesk/recharges',charge_body,uid=3);pid=charge['payment_id'];paybody={'request_key':key()}
            arm(f'/api/payments/{pid}/mock-confirm');await request(f'/api/payments/{pid}/mock-confirm',paybody,uid=3,expected=599)
            await start();await request(f'/api/payments/{pid}/mock-confirm',paybody,uid=3)
            await request(f'/api/payments/{pid}/mock-confirm',{'request_key':key()},uid=1)
            assert (await counts())['balance']==29500
            assert (await fetch_one(settings,"SELECT COUNT(*) AS n FROM member_account_transaction WHERE recharge_order_id=%s",(charge['id'],)))['n']==1
            assert (await request(f'/api/payments/{pid}',uid=3))['status']=='succeeded'
            checks.append('lost recharge creation/payment responses recover exactly one credit across restart and different staff retry')

            announcement_body={'title':'验收公告','content':'本条内容仅位于隔离测试库。','status':1}
            announcement=await request('/api/admin/announcements',announcement_body,uid=1)
            assert (await request('/api/announcements/'+str(announcement['id'])))['title']=='验收公告'
            await request('/api/admin/announcements',announcement_body,uid=3,expected=403)
            assert (await request('/api/announcements'))['total']==1
            await request('/api/admin/announcements/'+str(announcement['id'])+'/status',{'status':0},uid=1,method='PUT')
            await request('/api/announcements/'+str(announcement['id']),expected=404)
            assert (await request('/api/admin/announcements',uid=1))['total']==1
            checks.append('administrator announcement publishing/hiding works; frontdesk cannot publish and public hidden content is absent')

            event_day=str(date.today()+timedelta(days=3));deadline=str(date.today()+timedelta(days=2))
            event_body={'title':'隔离验收赛','content':'用于回归报名和取消。','location':'验收场地','start_at':event_day+' 15:00',
                'end_at':event_day+' 17:00','registration_deadline':deadline+' 18:00','capacity':2,'status':1}
            event=await request('/api/admin/events',event_body,uid=1);eid=event['id']
            await request('/api/admin/events',event_body,uid=3,expected=403)
            registered=await request(f'/api/events/{eid}/register',{});assert registered['is_registered'] and registered['registered_count']==1
            await request(f'/api/events/{eid}/register',{},expected=400)
            await request(f'/api/events/{eid}/register',{},uid=3,expected=403)
            canceled=await request(f'/api/events/{eid}/cancel-registration',{},method='PUT');assert not canceled['is_registered'] and canceled['registered_count']==0
            assert (await request('/api/events'))['total']==1
            checks.append('event publish, single registration, duplicate/role rejection and cancellation preserve registered count')

            post=await request('/api/community/posts',{'content':'隔离测试球友动态'})
            admin_post=await request('/api/community/posts',{'content':'隔离测试管理员发布'},uid=1)
            for uid in (3,4):await request('/api/community/posts',{'content':'不应写入'},uid=uid,expected=403)
            assert (await request('/api/community/posts'))['total']==2
            await request('/api/community/posts/'+str(admin_post['id'])+'/hide',{},method='PUT',expected=404)
            await request('/api/community/posts/'+str(post['id'])+'/hide',{},method='PUT')
            await request('/api/admin/community/posts/'+str(admin_post['id'])+'/hide',{},uid=1,method='PUT')
            assert (await request('/api/community/posts'))['total']==0
            assert (await request('/api/admin/community/posts',uid=1))['total']==2
            checks.append('customer and administrator community publishing, own hide and admin moderation work without staff content privileges')

            messages=await request('/api/notifications');assert messages['total']>0
            nid=messages['items'][0]['id'];unread=(await request('/api/notifications/unread-count'))['unread_count']
            await request(f'/api/notifications/{nid}/read',{},uid=3,method='PUT',expected=404)
            await request(f'/api/notifications/{nid}/read',{},method='PUT')
            await request(f'/api/notifications/{nid}/read',{},method='PUT')
            assert (await request('/api/notifications/unread-count'))['unread_count']==unread-1
            before_profile=await request('/api/auth/profile')
            updated=await request('/api/auth/profile',{'nickname':'回归测试球友','contact':'qa-contact'},method='PUT')
            assert updated['nickname']=='回归测试球友' and updated['contact']=='qa-contact'
            assert updated['member']==before_profile['member'] and updated['role']=='user'
            checks.append('notification ownership/idempotent read and editable profile preserve account balance, points and role')

            extension=await request('/api/frontdesk/walk-ins/'+str(walk['id'])+'/extensions',
                {'end_time':'16:00','expected_amount_cents':10000,'request_key':key()},uid=3)
            assert extension['status']=='pending'
            block=await request('/api/admin/court-blocks',{'court_id':1,'reserve_date':str(date.today()),'start_time':'16:00','end_time':'17:00','reason':'隔离维修占场','block_type':'maintenance'},uid=1)
            recommendation={'reserve_date':str(date.today()),'earliest_time':'14:00','duration_minutes':60,'preferred_court_id':1}
            choices=await request('/api/reservations/recommendations',recommendation)
            assert choices['items'][0]['start_time']=='17:00',choices
            await request('/api/admin/court-blocks/'+str(block['id'])+'/release',{},uid=1,method='PUT')
            choices=await request('/api/reservations/recommendations',recommendation)
            assert choices['items'][0]['start_time']=='16:00',choices
            assert (await request('/api/frontdesk/walk-ins/'+str(walk['id']),uid=3))['end_time']=='15:00'
            checks.append('recommendations exclude paid walk-in, pending extension and maintenance; release restores only the freed interval')
            print(json.dumps({'passed':True,'checks':checks,'backend_processes':restarts,'scope':'actual loopback HTTP TCP drops after service commit; owned disposable DB; browser UI not covered'},ensure_ascii=False,indent=2))
        finally:
            await stop();client.close();await close_pool()
            if created:
                async with con.cursor() as cur:await cur.execute(f'DROP DATABASE `{name}`')
            con.close()

if __name__=='__main__':asyncio.run(serve(sys.argv[2]) if len(sys.argv)>1 and sys.argv[1]=='--serve' else run())
