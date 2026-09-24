"""Recharge invariants against an owned, disposable MySQL database."""
import asyncio
from dataclasses import replace
from datetime import datetime
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
from repositories import database, recharge_repository as repo
from repositories.database import execute,fetch_one,fetch_all,close_pool
from repositories.payment_common import MAX_CENTS
from services import recharge_service as service,payment_service,member_service
from utils.response import ApiError

async def run():
 s=replace(load_settings(),mysql_database='badminton_demo_recharge_'+secrets.token_hex(8))
 name=s.mysql_database;created=False;checks=[];now=datetime(2026,10,1,14,10)
 con=await aiomysql.connect(host=s.mysql_host,port=s.mysql_port,user=s.mysql_user,password=s.mysql_password,autocommit=True)
 admin={'id':1,'username':'admin_test','role':'admin'};user={'id':2,'username':'customer','role':'user'}
 desk={'id':4,'username':'desk','role':'frontdesk'};otherdesk={'id':6,'username':'otherdesk','role':'frontdesk'}
 repair={'id':5,'username':'repair','role':'maintenance'}
 def body(amount=10000,uid=2,key=None):return {'user_id':uid,'amount_cents':amount,'request_key':key or secrets.token_hex(12)}
 async def create(payload=None,actor=desk):return await service.create(s,actor,payload or body())
 async def pay(order,actor=desk,action='mock_confirm',key=None):return await payment_service.act(s,actor,order['payment_id'],action,{'request_key':key or secrets.token_hex(12)})
 async def state():return [await fetch_all(s,'SELECT * FROM '+table+' ORDER BY '+key) for table,key in [('recharge_order','id'),('payment_order','id'),('payment_command','id'),('member_account','user_id'),('member_account_transaction','id'),('notification','id'),('operation_log','id')]]
 async def reject(coro,code=409):
  try:await coro
  except ApiError as e:assert e.status_code==code,(e.status_code,e.message)
  else:raise AssertionError('Expected rejection')
 async def account(uid=2):return await fetch_one(s,'SELECT * FROM member_account WHERE user_id=%s',(uid,))
 async def fault(coro,method):
  before=await state()
  with patch.object(repo,method,AsyncMock(side_effect=RuntimeError('injected failure'))):
   try:await coro
   except RuntimeError:pass
   else:raise AssertionError('Expected injected failure')
  assert await state()==before
 try:
  async with con.cursor() as cur:
   await cur.execute(f'CREATE DATABASE `{name}` CHARACTER SET utf8mb4');created=True
   await cur.execute(f'USE `{name}`')
   for stmt in (ROOT/'sql/init.sql').read_text().split(';'):
    if re.match(r'^CREATE TABLE',stmt.strip()):await cur.execute(stmt)
  database._pool=await aiomysql.create_pool(host=s.mysql_host,port=s.mysql_port,user=s.mysql_user,password=s.mysql_password,db=name,minsize=1,maxsize=25,autocommit=True,init_command=f'SET timestamp={int(now.timestamp())}')
  await execute(s,"INSERT INTO user(id,username,password_hash,contact,role) VALUES (1,'admin_test','unused',NULL,'admin'),(2,'customer','unused','13800138000','user'),(3,'other','unused',NULL,'user'),(4,'desk','unused',NULL,'frontdesk'),(5,'repair','unused',NULL,'maintenance'),(6,'otherdesk','unused',NULL,'frontdesk')")
  await execute(s,"INSERT INTO member_account(user_id,member_level,balance_cents,points,expires_at) VALUES (1,'normal',0,0,NULL),(2,'gold',0,42,'2027-10-01'),(3,'normal',0,0,NULL),(4,'normal',0,0,NULL),(5,'normal',0,0,NULL),(6,'normal',0,0,NULL)")
  found=await service.find_customers(s,desk,'13800138000');assert len(found['items'])==1
  assert found['items'][0]=={'id':2,'username':'customer','nickname':None,'contact_masked':'138****8000','balance_cents':0}
  assert (await service.find_customers(s,desk,'%'))['items']==[]
  assert (await service.find_customers(s,desk,'cust'))['items']==[]
  for actor in (user,repair):await reject(service.find_customers(s,actor,'customer'),403)
  await reject(service.find_customers(s,desk,''),400)
  before=await state()
  for amount in (0,-1,True,1.5,'100',None,MAX_CENTS+1):await reject(create(body(amount=amount)),400)
  for uid in (0,-1,True,1.5,'2',None):await reject(create(body(uid=uid)),400)
  await reject(create({**body(),'points':10}),400)
  await reject(create(body(uid=999)),404)
  await reject(create(body(uid=4)))
  await execute(s,'UPDATE user SET status=0 WHERE id=3')
  await reject(create(body(uid=3)))
  await execute(s,'UPDATE user SET status=1 WHERE id=3')
  # updated_at is unchanged under fixed clock, no business effects for invalid requests.
  assert await state()==before
  checks.append('exact customer lookup, masked data, invalid targets/amounts/rights rejected without writes')

  payload=body(key='same-create-0001');baseline=await account()
  await fault(create(payload),'audit')
  orders=await asyncio.gather(*[create(payload) for _ in range(12)]);o=orders[0]
  assert len({v['id'] for v in orders})==1 and o['status']=='pending' and o['credit'] is None
  assert await account()==baseline
  await reject(create({**payload,'amount_cents':10001}))
  await reject(create({**payload,'user_id':3}))
  await reject(repo.get(s,otherdesk,o['id']),404)
  for actor in (user,repair):
   await reject(payment_service.get(s,actor,o['payment_id']),403)
   await reject(pay(o,actor),403)
  await reject(pay(o,otherdesk),404)
  await reject(pay(o,admin,action='balance_pay'))
  await execute(s,"UPDATE user SET role='user' WHERE id=4")
  await reject(pay(o),403)
  await execute(s,"UPDATE user SET role='frontdesk' WHERE id=4")
  checks.append('stable create is once, same-key changes rejected, customer cannot self recharge, actor scope and fresh role enforced')

  await pay(o,action='mock_fail',key='attempt-fail-0001');assert await account()==baseline
  assert (await repo.get(s,desk,o['id']))['status']=='pending'
  await reject(pay(o,key='attempt-fail-0001'))
  await execute(s,'UPDATE user SET status=0 WHERE id=2');await reject(pay(o));await execute(s,'UPDATE user SET status=1 WHERE id=2')
  await execute(s,"UPDATE user SET role='maintenance' WHERE id=2");await reject(pay(o));await execute(s,"UPDATE user SET role='user' WHERE id=2")
  for method in ('notification','audit'):await fault(pay(o),method)
  before=await state()
  with patch('repositories.recharge_repository.money.save_command',AsyncMock(side_effect=RuntimeError('lost receipt write'))):
   try:await pay(o)
   except RuntimeError:pass
   else:raise AssertionError('Expected receipt fault')
  assert await state()==before
  results=await asyncio.gather(*[pay(o,actor=admin if i%2 else desk) for i in range(20)],return_exceptions=True)
  assert all(isinstance(v,dict) and v['status']=='paid' for v in results),results
  current=await account();assert current['balance_cents']==10000
  for field in ('points','member_level','expires_at'):assert current[field]==baseline[field]
  assert (await account(4))['balance_cents']==0
  ledger=await fetch_all(s,"SELECT * FROM member_account_transaction WHERE recharge_order_id=%s",(o['id'],));assert len(ledger)==1
  assert ledger[0]['balance_before_cents']==0 and ledger[0]['balance_after_cents']==10000 and ledger[0]['points_change']==0
  assert all(v['credit']['operator_id']==ledger[0]['operator_id'] for v in results)
  queried=await payment_service.get(s,desk,o['payment_id']);assert queried['business_type']=='recharge' and queried['credit']['balance_after_cents']==10000
  await reject(service.cancel(s,desk,o['id'],{'request_key':'cancel-paid-0001'}))
  checks.append('failure and deactivated targets do not credit, injected faults roll back, 20 simultaneous confirms credit once and preserve membership')

  second=await create(body(amount=1200));third=await create(body(amount=1300),actor=otherdesk)
  await asyncio.gather(pay(second),pay(third,otherdesk))
  effects=await fetch_all(s,"SELECT balance_before_cents,balance_after_cents FROM member_account_transaction WHERE user_id=2 ORDER BY id")
  assert (await account())['balance_cents']==12500 and all(effects[i]['balance_before_cents']==effects[i-1]['balance_after_cents'] for i in range(1,len(effects)))
  all_rows=await service.list_orders(s,admin,{'page_size':'1'});assert all_rows['total']==3 and len(all_rows['items'])==1
  desk_rows=await service.list_orders(s,desk,{});assert desk_rows['total']==2
  other_rows=await service.list_orders(s,otherdesk,{});assert other_rows['total']==1
  filtered=await service.list_orders(s,admin,{'order_no':third['payment_no'],'status':'paid','date_from':'2026-10-01','date_to':'2026-10-01'});assert filtered['total']==1
  own=await member_service.list_my_transactions(s,current_user=user,type_arg='staff_recharge',page=1,page_size=20,offset=0)
  assert own['total']==3 and all(x['transaction_type_label']=='柜台储值' and x['recharge_order_id'] for x in own['items'])
  logs=await fetch_all(s,"SELECT detail FROM operation_log WHERE module='recharge'");assert '13800138000' not in json.dumps(logs)
  checks.append('different counter orders serialize wallet effects, staff sees own receipts and admin sees all, customer ledger links recharge')

  cancel_order=await create();before=await account()
  await fault(service.cancel(s,desk,cancel_order['id'],{'request_key':'cancel-once-0001'}),'audit')
  await asyncio.gather(*[service.cancel(s,desk,cancel_order['id'],{'request_key':f'cancel-repeat-{i:04d}'}) for i in range(4)])
  await reject(pay(cancel_order));assert await account()==before
  exp=await create();await execute(s,"UPDATE recharge_order SET expires_at=NOW() WHERE id=%s",(exp['id'],))
  assert (await repo.get(s,desk,exp['id']))['status']=='expired';await reject(pay(exp));assert await account()==before
  pending=await create();await execute(s,"UPDATE payment_order SET expires_at=NOW() WHERE id=%s",(pending['payment_id'],))
  assert await repo.expire(s)==1 and await repo.expire(s)==0
  checks.append('cancel/expiry close business and payment once, never credit; receipt failure leaves cancellation retryable')

  await execute(s,'UPDATE member_account SET balance_cents=%s WHERE user_id=2',(MAX_CENTS-100,))
  await reject(create(body(amount=101)))
  upper_a=await create(body(amount=100));upper_b=await create(body(amount=100))
  await pay(upper_a);await reject(pay(upper_b))
  assert (await account())['balance_cents']==MAX_CENTS and (await repo.get(s,desk,upper_b['id']))['status']=='pending'
  await service.cancel(s,desk,upper_b['id'],{'request_key':'cancel-overflow-0001'})
  checks.append('create and confirmation both check integer balance ceiling; competing pending credits cannot overflow')

  await execute(s,'UPDATE member_account SET balance_cents=0 WHERE user_id=2')
  race=await create(body(amount=1000))
  outcomes=await asyncio.gather(pay(race),service.cancel(s,desk,race['id'],{'request_key':'race-cancel-0001'}),return_exceptions=True)
  final=await repo.get(s,desk,race['id']);acct=await account()
  assert final['status'] in ('paid','canceled') and acct['balance_cents']==(1000 if final['status']=='paid' else 0)
  assert sum(isinstance(v,ApiError) for v in outcomes)==1
  checks.append('payment vs cancellation race reaches one legal terminal state and matching credit')
  print(json.dumps({'passed':len(checks),'checks':checks,'database_scope':'owned disposable database only'},ensure_ascii=False,indent=2))
 finally:
  await close_pool()
  if created:
   async with con.cursor() as cur:await cur.execute(f'DROP DATABASE `{name}`')
  con.close()
if __name__=='__main__':asyncio.run(run())
