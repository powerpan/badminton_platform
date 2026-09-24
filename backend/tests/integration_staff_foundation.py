"""Disposable MySQL migration/role/maintenance integration; no business DB writes."""
import asyncio
from dataclasses import replace
from datetime import date, datetime, timedelta
import importlib.util
import json
from pathlib import Path
import re
import secrets
import shutil
import sys
import tempfile
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
from dotenv import load_dotenv
load_dotenv(ROOT/'backend/.env')
import aiomysql
from config.settings import load_settings
from repositories.database import close_pool, execute, fetch_all, fetch_one
from services import admin_user_service, booking_operations_service as ops, recharge_service, payment_service, shop_service

spec=importlib.util.spec_from_file_location('staff_migration',ROOT/'scripts/migrate_staff_payments.py')
migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)


async def structure(cursor, name):
    columns,indexes,constraints=await migration.schema(cursor,name)
    def clean(row): return {k:v for k,v in row.items() if k not in ('TABLE_SCHEMA',)}
    await cursor.execute("""SELECT TABLE_NAME,CONSTRAINT_NAME,COLUMN_NAME,ORDINAL_POSITION,REFERENCED_TABLE_NAME,REFERENCED_COLUMN_NAME
        FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA=%s ORDER BY TABLE_NAME,CONSTRAINT_NAME,ORDINAL_POSITION""", (name,))
    keys = await cursor.fetchall()
    return columns,indexes,constraints,keys


async def verify_backup_restore(settings, con, source, restored, created):
    """Exercise real mysqldump/mysql on caller-owned databases; never log credentials."""
    dump_bin, mysql_bin = shutil.which('mysqldump'), shutil.which('mysql')
    if not dump_bin or not mysql_bin:
        raise RuntimeError('备份恢复验收需要本机 mysqldump 与 mysql 客户端')
    assert source in created and restored not in created
    async with con.cursor(aiomysql.DictCursor) as cursor:
        await cursor.execute(f'USE `{source}`')
        columns,_,_=await migration.schema(cursor,source)
        before=await migration.fingerprints(cursor,columns)
        definition=await structure(cursor,source)
        await cursor.execute(f'CREATE DATABASE `{restored}` CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci')
        created.append(restored)
    def option(value):return '"'+str(value).replace('\\','\\\\').replace('"','\\"').replace('\n','\\n')+'"'
    with tempfile.TemporaryDirectory(prefix='bf-migration-restore-') as temp:
        config=Path(temp)/'client.cnf'
        config.touch(mode=0o600)
        config.write_text('[client]\n'+''.join(name+'='+option(value)+'\n' for name,value in (
            ('host',settings.mysql_host),('port',settings.mysql_port),('user',settings.mysql_user),('password',settings.mysql_password))))
        dump=Path(temp)/'backup.sql'
        with dump.open('wb') as output:
            process=await asyncio.create_subprocess_exec(dump_bin,'--defaults-extra-file='+str(config),'--single-transaction',
                '--skip-comments','--hex-blob','--set-gtid-purged=OFF',source,stdout=output,stderr=asyncio.subprocess.PIPE)
            _,error=await process.communicate()
            assert process.returncode==0,'mysqldump failed; check local client compatibility (credentials withheld)'
        assert dump.stat().st_size>0
        with dump.open('rb') as input_file:
            process=await asyncio.create_subprocess_exec(mysql_bin,'--defaults-extra-file='+str(config),restored,
                stdin=input_file,stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.PIPE)
            _,error=await process.communicate()
            assert process.returncode==0,'mysql restore failed (credentials withheld)'
    async with con.cursor(aiomysql.DictCursor) as cursor:
        await cursor.execute(f'USE `{restored}`')
        assert definition==await structure(cursor,restored),'restored schema differs'
        assert before==await migration.fingerprints(cursor,columns),'restored data differs'


async def run():
    settings=load_settings()
    con=await aiomysql.connect(host=settings.mysql_host,port=settings.mysql_port,user=settings.mysql_user,password=settings.mysql_password,autocommit=True)
    prefix='badminton_demo_staff_'+datetime.now().strftime('%Y%m%d%H%M%S')+'_'+secrets.token_hex(3)
    old,new=prefix+'_old',prefix+'_new'
    created=[]; checks=[]
    try:
        async with con.cursor(aiomysql.DictCursor) as cur:
            for name,sql in [(old,(ROOT/'backend/tests/fixtures/phase7_schema.sql').read_text()),(new,(ROOT/'sql/init.sql').read_text())]:
                await cur.execute(f'CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci');created.append(name)
                await cur.execute(f'USE `{name}`')
                for statement in re.findall(r'CREATE TABLE IF NOT EXISTS \w+ \(.*?\) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;',sql,re.S):
                    await cur.execute(statement)
            await cur.execute(f'USE `{old}`')
            await cur.execute("INSERT INTO user(id,username,password_hash,role) VALUES (1,'qa_admin','test-only','admin'),(2,'qa_customer','test-only','user')")
            await cur.execute("INSERT INTO member_account(user_id,balance_cents,points) VALUES (1,0,0),(2,27001,351)")
            await cur.execute("INSERT INTO court(id,court_no,court_name) VALUES (1,'QA1','测试场地')")
            await cur.execute("INSERT INTO reservation(id,reservation_no,user_id,court_id,reserve_date,start_time,end_time,time_slot,status) VALUES (1,'QA-LEGACY',2,1,'2025-01-01','14:00','15:00','14:00-15:00','confirmed')")
            await cur.execute("INSERT INTO reservation_order(order_no,reservation_id,user_id,status,expires_at,paid_at,amount_cents) VALUES ('QA-LEGACY-O',1,2,'paid','2025-01-01 13:00','2025-01-01 12:55',12000)")
            await cur.execute("INSERT INTO shop_product(id,product_no,product_name,price_cents,stock,sold_count) VALUES (1,'QA-P','测试商品',1800,28,2)")
            await cur.execute("INSERT INTO shop_order(id,order_no,user_id,status,total_amount_cents,paid_at) VALUES (1,'QA-S',2,'paid',3600,'2025-01-01 12:55')")
            await cur.execute("INSERT INTO shop_order_item(order_id,product_id,product_no_snapshot,product_name_snapshot,price_cents,quantity,subtotal_cents) VALUES (1,1,'QA-P','测试商品',1800,2,3600)")
            await cur.execute("INSERT INTO member_account_transaction(user_id,shop_order_id,transaction_type,balance_change_cents,balance_before_cents,balance_after_cents) VALUES (2,1,'shop_charge',-3600,30601,27001)")
            await cur.execute("INSERT INTO court_block(court_id,reserve_date,start_time,end_time,reason,created_by) VALUES (1,'2026-10-01','09:00','10:00','旧维修字样不能自动归类',1)")
        preview=await migration.migrate(old)
        assert preview['planned_statements'] and preview['existing_data_unchanged'] is None
        await verify_backup_restore(settings,con,old,prefix+'_backup7',created)
        checks.append('real SQL backup/restore preserves all phase7 rows and schema')
        executed=0
        original_execute=aiomysql.DictCursor.execute
        async def interrupted(cursor,query,args=None):
            nonlocal executed
            result=await original_execute(cursor,query,args)
            if query.startswith(('CREATE TABLE','ALTER TABLE')):
                executed+=1
                if executed==10:raise RuntimeError('injected migration interruption after committed DDL')
            return result
        with patch.object(aiomysql.DictCursor,'execute',interrupted):
            try:await migration.migrate(old,True)
            except RuntimeError as error:assert str(error)=='injected migration interruption after committed DDL'
            else:raise AssertionError('migration should have been interrupted')
        pending=await migration.migrate(old)
        assert len(pending['planned_statements'])==len(preview['planned_statements'])-10
        first=await migration.migrate(old,True)
        second=await migration.migrate(old,True)
        assert first['existing_data_unchanged'] and second['applied_count']==0
        assert first['before']['member_account']['rows']==2
        async with con.cursor(aiomysql.DictCursor) as cur:
            original_columns,_,_=await migration.schema(cur,prefix+'_backup7')
            await cur.execute(f'USE `{old}`')
            assert await migration.fingerprints(cur,original_columns)==preview['before']
        checks.append('migration interrupted after 10 committed DDL statements resumes remaining actions exactly once')
        checks.append('legacy row fingerprints conserved; repeat applies zero DDL')
        async with con.cursor(aiomysql.DictCursor) as cur:
            assert await structure(cur,old)==await structure(cur,new), 'fresh/upgrade schema differs'
        checks.append(f'all {len(migration.target_tables())} tables: column definitions, indexes, FK definitions match fresh init')
        test_settings=replace(settings,mysql_database=old)
        row=await fetch_one(test_settings,'SELECT source,operator_id,opened_at FROM reservation WHERE id=1')
        assert row=={'source':'online','operator_id':None,'opened_at':None}
        assert (await fetch_one(test_settings,'SELECT block_type FROM court_block WHERE id=1'))['block_type']=='legacy_unspecified'
        for table in migration.NEW_TABLES:
            assert (await fetch_one(test_settings,f'SELECT COUNT(*) AS n FROM `{table}`'))['n']==0
        checks.append('legacy channels, actors and payment/pickup evidence are not fabricated')
        for role in ('frontdesk','maintenance'):
            result=await admin_user_service.create_user(test_settings,{'username':'qa_'+role,'password':secrets.token_urlsafe(18),'role':role})
            assert result['role']==role
        checks.append('admin creates frontdesk and maintenance accounts via service')
        actor={'id':1,'username':'qa_admin','role':'admin'}
        target={'court_id':1,'reserve_date':str(date.today()+timedelta(days=2)),'start_time':'09:00','end_time':'10:00'}
        # Existing config defaults suffice; all records are synthetic.
        block=await ops.create_block(test_settings,{**target,'reason':'地胶检查','block_type':'maintenance'},actor)
        await ops.create_block(test_settings,{**target,'start_time':'10:00','end_time':'11:00','reason':'测试包场','block_type':'private_booking'},actor)
        data=await ops.maintenance_blocks(test_settings,target['reserve_date'],target['reserve_date'])
        assert [r['id'] for r in data['items']]==[block['id']]
        assert data['items'][0]['schedule_status']=='scheduled'
        await ops.operations.classify_block(test_settings,block['id'],'private_booking',actor)
        assert not (await ops.maintenance_blocks(test_settings,target['reserve_date'],target['reserve_date']))['items']
        audit=await fetch_all(test_settings,"SELECT action FROM operation_log WHERE action='classify_block'")
        assert len(audit)==1
        await ops.operations.classify_block(test_settings,block['id'],'private_booking',actor)
        assert len(await fetch_all(test_settings,"SELECT action FROM operation_log WHERE action='classify_block'"))==1
        checks.append('repair-only queries, explicit reclassification and idempotent audit')
        desk=await fetch_one(test_settings,"SELECT id,username,role FROM user WHERE username='qa_frontdesk'")
        customer={'id':2,'username':'qa_customer','role':'user'}
        key=lambda:secrets.token_hex(12)
        recharge=await recharge_service.create(test_settings,desk,{'user_id':2,'amount_cents':10000,'request_key':key()})
        await payment_service.act(test_settings,desk,recharge['payment_id'],'mock_confirm',{'request_key':key()})
        order=await shop_service.create_order(test_settings,current_user=customer,body={'items':[{'product_id':1,'quantity':1,'expected_price_cents':1800}],'pay_method':'mock_alipay','request_key':key()})
        await payment_service.act(test_settings,customer,order['payment_id'],'mock_confirm',{'request_key':key()})
        await shop_service.admin_cancel_order(test_settings,current_user=actor,order_id=order['id'],body={'request_key':key()})
        for table in migration.NEW_TABLES:
            assert (await fetch_one(test_settings,f'SELECT COUNT(*) AS n FROM `{table}`'))['n']>0
        await verify_backup_restore(settings,con,old,prefix+'_backup8',created)
        checks.append('real SQL backup/restore preserves phase8 schema, staff roles, recharge, payment/refund, pickup/holds and audit records')
        print(json.dumps({'passed':True,'checks':checks,'migration_statements':len(preview['planned_statements']),
            'interrupted_after':10,'resumed_statements':first['applied_count'],'database_scope':'disposable only'},ensure_ascii=False,indent=2))
    finally:
        await close_pool()
        async with con.cursor() as cur:
            for name in reversed(created): await cur.execute(f'DROP DATABASE `{name}`')
        con.close()

if __name__=='__main__': asyncio.run(run())
