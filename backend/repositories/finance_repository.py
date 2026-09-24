"""Read-only financial projection. Payment facts and wallet effects are not added twice."""
import json

from repositories.transaction import transaction
from repositories.admin_booking_repository import contains
from utils.response import ApiError
from utils.staff_booking import json_value

RECORD_TYPES = ('payment','refund','account','legacy_reservation','legacy_shop')
COLUMNS = ('record_type','record_id','occurred_at','business_type','entry_type','status','pay_method',
    'amount_cents','confirmed','evidence','customer_user_id','customer_username','customer_name','customer_contact',
    'operator_id','operator_name','created_by','created_by_name','reservation_id','reservation_no',
    'shop_order_id','recharge_order_id','order_no','payment_order_id','payment_no','payment_refund_id','refund_no',
    'balance_change_cents','points_change','description')
PAYMENT_FROM = ''' FROM payment_order p
    LEFT JOIN reservation_order ro ON ro.id=p.reservation_order_id
    LEFT JOIN reservation r ON r.id=ro.reservation_id
    LEFT JOIN shop_order so ON so.id=p.shop_order_id
    LEFT JOIN recharge_order rc ON rc.id=p.recharge_order_id
    LEFT JOIN user customer ON customer.id=p.customer_user_id
    LEFT JOIN payment_command collected ON collected.id=(SELECT MIN(pc.id) FROM payment_command pc
        WHERE pc.payment_order_id=p.id AND pc.action IN ('mock_confirm','balance_pay') AND p.paid_at IS NOT NULL)
    LEFT JOIN user collector ON collector.id=collected.operator_id '''
BASE_BUSINESS = """CASE WHEN p.recharge_order_id IS NOT NULL THEN 'recharge'
    WHEN p.shop_order_id IS NOT NULL THEN 'shop' WHEN r.source='online' THEN 'reservation' ELSE r.source END"""
BUSINESS = f"IF(p.purpose='reschedule','reschedule',({BASE_BUSINESS}))"
KNOWN_ACCOUNT_TYPES = "('admin_adjust','reservation_charge','reservation_refund','reservation_reschedule','shop_purchase','shop_refund')"
ACCOUNT_VALID = f'''(mt.transaction_type IN {KNOWN_ACCOUNT_TYPES}
    AND mt.balance_after_cents-mt.balance_before_cents=mt.balance_change_cents
    AND mt.points_after-mt.points_before=mt.points_change
    AND (mt.reservation_id IS NULL OR r.user_id=mt.user_id)
    AND (mt.shop_order_id IS NULL OR so.user_id=mt.user_id)
    AND (mt.transaction_type='admin_adjust'
        OR (mt.transaction_type IN ('reservation_charge','reservation_refund','reservation_reschedule') AND r.id IS NOT NULL)
        OR (mt.transaction_type IN ('shop_purchase','shop_refund') AND so.id IS NOT NULL))
    AND (mt.transaction_type='admin_adjust' OR mt.balance_change_cents<=0 OR EXISTS (
        SELECT 1 FROM member_account_transaction original WHERE original.user_id=mt.user_id
        AND ((mt.reservation_id IS NOT NULL AND original.reservation_id=mt.reservation_id AND original.transaction_type='reservation_charge')
            OR (mt.shop_order_id IS NOT NULL AND original.shop_order_id=mt.shop_order_id AND original.transaction_type='shop_purchase'))
        AND original.balance_change_cents<0 AND original.balance_after_cents-original.balance_before_cents=original.balance_change_cents)))'''


def literal(value):
    # Only code-owned enum/label literals are passed here; user values are SQL parameters.
    return "'" + value.replace("'", "''") + "'"


def source_specs():
    common = dict(customer_user_id='p.customer_user_id',customer_username='customer.username',
        customer_name='COALESCE(r.guest_name,customer.nickname,customer.username)',
        customer_contact='COALESCE(r.guest_contact,customer.contact)',
        created_by='p.operator_id',created_by_name='p.operator_name_snapshot',
        reservation_id='r.id',reservation_no='r.reservation_no',shop_order_id='so.id',recharge_order_id='rc.id',
        order_no='COALESCE(ro.order_no,so.order_no,rc.recharge_no)',payment_order_id='p.id',payment_no='p.payment_no')
    payment = {**common,'record_type':literal('payment'),'record_id':'p.id',
        'occurred_at':'COALESCE(p.paid_at,p.closed_at,p.created_at)', 'business_type':BUSINESS,
        'entry_type':"IF(p.recharge_order_id IS NULL,'collection','recharge')",'status':'p.status','pay_method':'p.pay_method',
        'amount_cents':'p.amount_cents','confirmed':"p.paid_at IS NOT NULL AND p.status IN ('succeeded','refunded')",
        'evidence':literal('payment'),
        'operator_id':'IF(p.paid_at IS NULL,p.operator_id,collected.operator_id)',
        'operator_name':'IF(p.paid_at IS NULL,p.operator_name_snapshot,collector.username)',
        'description':"CASE WHEN p.recharge_order_id IS NOT NULL THEN '柜台储值' WHEN p.purpose='reschedule' THEN '改期补差' ELSE '业务收款' END"}
    refund = {**common,'record_type':literal('refund'),'record_id':'rf.id','occurred_at':'rf.refunded_at',
        'business_type':f"IF(rf.purpose='reschedule','reschedule',({BASE_BUSINESS}))",'entry_type':literal('refund'),
        'status':'rf.status','pay_method':'p.pay_method','amount_cents':'-rf.amount_cents',
        'confirmed':"rf.status='succeeded' AND p.paid_at IS NOT NULL",'evidence':literal('payment'),
        'operator_id':'rf.operator_id','operator_name':'rf.operator_name_snapshot',
        'payment_refund_id':'rf.id','refund_no':'rf.refund_no','description':'rf.reason'}
    account = {'record_type':literal('account'),'record_id':'mt.id','occurred_at':'mt.created_at',
        'business_type':"""CASE WHEN mt.transaction_type='admin_adjust' THEN 'adjustment'
            WHEN mt.transaction_type='reservation_reschedule' THEN 'reschedule'
            WHEN mt.shop_order_id IS NOT NULL THEN 'shop' WHEN r.source='online' THEN 'reservation' ELSE r.source END""",
        'entry_type':f"""CASE WHEN NOT {ACCOUNT_VALID} THEN 'unverified' WHEN mt.transaction_type='admin_adjust' THEN 'adjustment'
            WHEN mt.balance_change_cents=0 THEN 'points' WHEN mt.balance_change_cents<0 THEN 'collection' ELSE 'refund' END""",
        'status':f"IF({ACCOUNT_VALID},'recorded','unverified')",
        'pay_method':"IF(mt.transaction_type='admin_adjust','manual','balance')",
        'amount_cents':"IF(mt.transaction_type='admin_adjust',mt.balance_change_cents,-mt.balance_change_cents)",
        'confirmed':ACCOUNT_VALID,'evidence':literal('account'),
        'customer_user_id':'mt.user_id','customer_username':'customer.username','customer_name':'COALESCE(customer.nickname,customer.username)',
        'customer_contact':'customer.contact','operator_id':'mt.operator_id','operator_name':'mt.operator_username',
        'reservation_id':'r.id','reservation_no':'r.reservation_no','shop_order_id':'so.id',
        'order_no':'COALESCE(ro.order_no,so.order_no)', 'balance_change_cents':'mt.balance_change_cents',
        'points_change':'mt.points_change','description':'mt.reason'}
    account_from = ''' FROM member_account_transaction mt
        LEFT JOIN user customer ON customer.id=mt.user_id
        LEFT JOIN reservation r ON r.id=mt.reservation_id
        LEFT JOIN reservation_order ro ON ro.reservation_id=r.id
        LEFT JOIN shop_order so ON so.id=mt.shop_order_id '''
    legacy_common = {'entry_type':literal('unverified'),'status':literal('unverified'),'confirmed':'0',
        'evidence':literal('missing'),'customer_username':'customer.username',
        'description':literal('历史业务缺少可核对的收款凭据；金额不计入已确认汇总')}
    legacy_booking = {**legacy_common,'record_type':literal('legacy_reservation'),'record_id':'r.id',
        'occurred_at':'COALESCE(ro.paid_at,r.created_at)','business_type':"IF(r.source='online','reservation',r.source)",
        'pay_method':"COALESCE(ro.pay_method,'unknown')",'amount_cents':'COALESCE(ro.amount_cents,r.payable_amount_cents)',
        'customer_user_id':'r.user_id','customer_name':'COALESCE(r.guest_name,customer.nickname,customer.username)',
        'customer_contact':'COALESCE(r.guest_contact,customer.contact)', 'created_by':'r.operator_id',
        'created_by_name':'r.operator_name_snapshot','reservation_id':'r.id','reservation_no':'r.reservation_no','order_no':'ro.order_no'}
    legacy_shop = {**legacy_common,'record_type':literal('legacy_shop'),'record_id':'so.id',
        'occurred_at':'COALESCE(so.paid_at,so.created_at)','business_type':literal('shop'),'pay_method':'so.pay_method',
        'amount_cents':'so.total_amount_cents','customer_user_id':'so.user_id','customer_name':'COALESCE(customer.nickname,customer.username)',
        'customer_contact':'customer.contact','created_by':'so.operator_id','shop_order_id':'so.id','order_no':'so.order_no'}
    return {
        'payment':(payment,PAYMENT_FROM,'1=1'),
        'refund':(refund,PAYMENT_FROM+' JOIN payment_refund rf ON rf.payment_order_id=p.id ','1=1'),
        'account':(account,account_from,'mt.payment_order_id IS NULL AND mt.payment_refund_id IS NULL'),
        'legacy_reservation':(legacy_booking,''' FROM reservation r LEFT JOIN reservation_order ro ON ro.reservation_id=r.id
            LEFT JOIN user customer ON customer.id=r.user_id ''',"""(ro.paid_at IS NOT NULL OR ro.status='paid' OR r.status IN ('confirmed','completed'))
            AND NOT EXISTS (SELECT 1 FROM payment_order p WHERE p.reservation_order_id=ro.id)
            AND NOT EXISTS (SELECT 1 FROM member_account_transaction mt WHERE mt.reservation_id=r.id
                AND mt.user_id=r.user_id AND mt.transaction_type='reservation_charge' AND mt.balance_change_cents<0
                AND mt.balance_after_cents-mt.balance_before_cents=mt.balance_change_cents)"""),
        'legacy_shop':(legacy_shop,''' FROM shop_order so LEFT JOIN user customer ON customer.id=so.user_id ''',"""(so.paid_at IS NOT NULL OR so.status IN ('paid','refund_requested','completed'))
            AND NOT EXISTS (SELECT 1 FROM payment_order p WHERE p.shop_order_id=so.id)
            AND NOT EXISTS (SELECT 1 FROM member_account_transaction mt WHERE mt.shop_order_id=so.id
                AND mt.user_id=so.user_id AND mt.transaction_type='shop_purchase' AND mt.balance_change_cents<0
                AND mt.balance_after_cents-mt.balance_before_cents=mt.balance_change_cents)""")}


def projection(filters, record_type=None, record_id=None):
    parts, args = [], []
    for kind,(mapping,from_sql,condition) in source_specs().items():
        if record_type and kind!=record_type: continue
        where = [condition]
        for field,op in (('date_from','>='),('date_until','<')):
            if filters.get(field):
                where.append(f"{mapping['occurred_at']}{op}%s"); args.append(filters[field])
        if record_id is not None:
            where.append(f"{mapping['record_id']}=%s"); args.append(record_id)
        parts.append('SELECT '+','.join(f"{mapping.get(column,'NULL')} AS {column}" for column in COLUMNS)+from_sql+' WHERE '+' AND '.join(where))
    return ' UNION ALL '.join(parts),args


def conditions(filters):
    where,args=[],[]
    for key in ('business_type','entry_type','pay_method','status'):
        if filters.get(key): where.append(f'f.{key}=%s');args.append(filters[key])
    for key,fields in (('customer',('customer_username','customer_name','customer_contact')),('operator',('operator_name',))):
        if filters.get(key):
            where.append('('+' OR '.join(f"f.{field} LIKE %s ESCAPE '!'" for field in fields)+')')
            args.extend([contains(filters[key])]*len(fields))
    if filters.get('order_no'):
        where.append('(f.order_no=%s OR f.reservation_no=%s OR f.payment_no=%s OR f.refund_no=%s)')
        args.extend([filters['order_no']]*4)
    return (' WHERE '+' AND '.join(where) if where else ''),args


def normalize(row):
    row=dict(row)
    for key,value in row.items():
        if value is not None and (key.endswith('_cents') or key in ('confirmed','points_change')): row[key]=int(value)
    return json_value(row)


SUMMARY_TERMS = {
    'channel_receipts_cents':"confirmed=1 AND pay_method='mock_alipay' AND entry_type IN ('collection','recharge')",
    'channel_refunds_cents':"confirmed=1 AND pay_method='mock_alipay' AND entry_type='refund'",
    'recharge_cents':"confirmed=1 AND entry_type='recharge'",
    'balance_consumption_cents':"confirmed=1 AND pay_method='balance' AND entry_type='collection'",
    'balance_refunds_cents':"confirmed=1 AND pay_method='balance' AND entry_type='refund'",
    'consumption_receipts_cents':"confirmed=1 AND entry_type='collection'",
    'consumption_refunds_cents':"confirmed=1 AND entry_type='refund'",
    'adjustment_increase_cents':"confirmed=1 AND entry_type='adjustment' AND amount_cents>0",
    'adjustment_decrease_cents':"confirmed=1 AND entry_type='adjustment' AND amount_cents<0",
}


async def list_page(settings, filters, page, page_size):
    sql,args=projection(filters);where,values=conditions(filters);args+=values
    base=' FROM ('+sql+') f'+where
    sums=','.join(f'COALESCE(SUM(IF({condition},ABS(amount_cents),0)),0) AS {name}' for name,condition in SUMMARY_TERMS.items())
    async with transaction(settings,read_only=True) as cursor:
        await cursor.execute('SELECT NOW() AS server_now');now=(await cursor.fetchone())['server_now']
        await cursor.execute("SELECT COUNT(*) AS total,COALESCE(SUM(status='unverified'),0) AS unverified_count,"+sums+base,args)
        aggregate={key:int(value) for key,value in (await cursor.fetchone()).items()}
        total=aggregate.pop('total')
        aggregate['channel_net_cents']=aggregate['channel_receipts_cents']-aggregate['channel_refunds_cents']
        aggregate['consumption_net_cents']=aggregate['consumption_receipts_cents']-aggregate['consumption_refunds_cents']
        reconciliation=await wallet_reconciliation(cursor,base,args)
        await cursor.execute('SELECT f.*'+base+' ORDER BY occurred_at DESC,record_type,record_id DESC LIMIT %s OFFSET %s',
            (*args,page_size,(page-1)*page_size))
        items=[normalize(row) for row in await cursor.fetchall()]
    return json_value({'items':items,'total':total,'page':page,'page_size':page_size,'summary':aggregate,
        'reconciliation':reconciliation,'server_now':now})


async def wallet_reconciliation(cursor,base,args):
    # Filtered financial records select the customer cohort. Each selected wallet
    # is checked against its COMPLETE ledger by ID, not just the date-filtered page.
    sql='''SELECT a.user_id,u.username,a.balance_cents,a.points,latest.id AS latest_id,
        latest.balance_after_cents AS recorded_balance_cents,latest.points_after AS recorded_points,
        EXISTS(SELECT 1 FROM member_account_transaction bad
            LEFT JOIN member_account_transaction previous ON previous.id=(SELECT MAX(pr.id)
                FROM member_account_transaction pr WHERE pr.user_id=bad.user_id AND pr.id<bad.id)
            WHERE bad.user_id=a.user_id AND (
                bad.balance_after_cents-bad.balance_before_cents<>bad.balance_change_cents
                OR bad.points_after-bad.points_before<>bad.points_change
                OR (previous.id IS NOT NULL AND (bad.balance_before_cents<>previous.balance_after_cents
                    OR bad.points_before<>previous.points_after)))) AS chain_mismatch
        FROM member_account a JOIN user u ON u.id=a.user_id
        LEFT JOIN member_account_transaction latest ON latest.id=(SELECT MAX(id) FROM member_account_transaction WHERE user_id=a.user_id)
        WHERE a.user_id IN (SELECT DISTINCT f.customer_user_id''' + base + ')'
    mismatch='(chain_mismatch=1 OR (latest_id IS NOT NULL AND (balance_cents<>recorded_balance_cents OR points<>recorded_points)))'
    await cursor.execute('SELECT COUNT(*) AS accounts,COALESCE(SUM(latest_id IS NULL),0) AS without_history,'+
        'COALESCE(SUM('+mismatch+'),0) AS mismatches FROM ('+sql+') wallets',args)
    summary={key:int(value) for key,value in (await cursor.fetchone()).items()}
    await cursor.execute('SELECT * FROM ('+sql+') wallets WHERE '+mismatch+' ORDER BY user_id LIMIT 20',args)
    summary['issues']=[normalize(row) for row in await cursor.fetchall()]
    return summary


async def detail(settings,record_type,record_id):
    sql,args=projection({},record_type,record_id)
    async with transaction(settings,read_only=True) as cursor:
        await cursor.execute(sql,args);record=await cursor.fetchone()
        if not record: raise ApiError(404,'流水记录不存在或已合并至对应支付凭据',404)
        result={'record':normalize(record)}
        rid,sid,cid=record['reservation_id'],record['shop_order_id'],record['recharge_order_id']
        if rid:
            await cursor.execute('''SELECT r.id,r.reservation_no,r.source,r.reserve_date,r.start_time,r.end_time,r.status,
                r.payable_amount_cents,r.root_reservation_id,r.parent_reservation_id,c.court_name
                FROM reservation r JOIN court c ON c.id=r.court_id WHERE r.id=%s''',(rid,))
        elif sid:
            await cursor.execute('SELECT id,order_no,status,total_amount_cents,paid_at,completed_at FROM shop_order WHERE id=%s',(sid,))
        elif cid:
            await cursor.execute('SELECT id,recharge_no,status,amount_cents,paid_at,operator_name_snapshot FROM recharge_order WHERE id=%s',(cid,))
        else:
            await cursor.execute('SELECT user_id,balance_cents,points,member_level,expires_at FROM member_account WHERE user_id=%s',(record['customer_user_id'],))
        result['business']=json_value(await cursor.fetchone())
        if sid:
            await cursor.execute('SELECT product_id,product_name_snapshot AS product_name,price_cents,quantity,subtotal_cents FROM shop_order_item WHERE order_id=%s ORDER BY id',(sid,))
            result['items']=list(await cursor.fetchall())
        # One business includes its supplements and refunds. The account-only case
        # stays scoped to that exact adjustment, rather than exposing unrelated history.
        if rid:
            pwhere='p.reservation_order_id IN (SELECT id FROM reservation_order WHERE reservation_id=%s)';value=rid
            twhere='reservation_id=%s'
        elif sid:
            pwhere='p.shop_order_id=%s';value=sid;twhere='shop_order_id=%s'
        elif cid:
            pwhere='p.recharge_order_id=%s';value=cid;twhere='recharge_order_id=%s'
        else:
            pwhere='1=0';value=None;twhere='id=%s'
        pvalues=(value,) if value is not None else ()
        await cursor.execute('''SELECT p.id,p.payment_no,p.amount_cents,p.pay_method,p.status,p.purpose,p.paid_at,
            p.created_at,p.operator_id,p.operator_name_snapshot,collected.operator_id AS collected_by,
            collector.username AS collector_username '''+PAYMENT_FROM+' WHERE '+pwhere+' ORDER BY p.id',pvalues)
        result['payments']=[normalize(row) for row in await cursor.fetchall()]
        await cursor.execute('''SELECT rf.id,rf.refund_no,rf.payment_order_id,rf.refund_group_no,rf.amount_cents,
            p.pay_method,rf.status,rf.purpose,rf.reason,rf.refunded_at,rf.operator_id,rf.operator_name_snapshot
            FROM payment_refund rf JOIN payment_order p ON p.id=rf.payment_order_id WHERE '''+pwhere+' ORDER BY rf.id',pvalues)
        result['refunds']=[normalize(row) for row in await cursor.fetchall()]
        await cursor.execute('''SELECT id,user_id,transaction_type,balance_change_cents,balance_before_cents,balance_after_cents,
            points_change,points_before,points_after,reason,operator_id,operator_username,created_at,payment_order_id,payment_refund_id
            FROM member_account_transaction WHERE '''+twhere+' ORDER BY created_at,id',(value if value is not None else record_id,))
        result['account_transactions']=[normalize(row) for row in await cursor.fetchall()]
        result['changes']=[]
        if rid:
            await cursor.execute('''SELECT id,before_snapshot,after_snapshot,balance_change_cents,settlement_delta_cents,pay_method,
                payment_order_id,refund_group_no,changed_by,created_at FROM reservation_change WHERE reservation_id=%s ORDER BY id''',(rid,))
            for row in await cursor.fetchall():
                for field in ('before_snapshot','after_snapshot'):row[field]=json.loads(row[field])
                result['changes'].append(normalize(row))
            court_ids=sorted({change[field]['court_id'] for change in result['changes'] for field in ('before_snapshot','after_snapshot')})
            if court_ids:
                await cursor.execute('SELECT id,court_no,court_name FROM court WHERE id IN ('+','.join(['%s']*len(court_ids))+')',court_ids)
                courts={court['id']:court for court in await cursor.fetchall()}
                for change in result['changes']:
                    for field in ('before_snapshot','after_snapshot'):
                        court=courts.get(change[field]['court_id'],{})
                        change[field].update(court_no=court.get('court_no'),court_name=court.get('court_name'))
        await cursor.execute('SELECT NOW() AS server_now');result['server_now']=json_value((await cursor.fetchone())['server_now'])
    return result


async def booking_reconciliation(settings,start,end):
    async with transaction(settings,read_only=True) as cursor:
        await cursor.execute('''SELECT r.id,r.payable_amount_cents,ro.status,ro.amount_cents,ro.paid_at,
            (SELECT COUNT(*) FROM payment_order p WHERE p.reservation_order_id=ro.id) AS payment_count,
            COALESCE((SELECT SUM(p.amount_cents) FROM payment_order p WHERE p.reservation_order_id=ro.id
                AND p.paid_at IS NOT NULL AND p.status IN ('succeeded','refunded')),0)
              -COALESCE((SELECT SUM(rf.amount_cents) FROM payment_refund rf JOIN payment_order p ON p.id=rf.payment_order_id
                WHERE p.reservation_order_id=ro.id AND rf.status='succeeded'),0) AS payment_net,
            COALESCE((SELECT -SUM(mt.balance_change_cents) FROM member_account_transaction mt
                WHERE mt.reservation_id=r.id AND mt.transaction_type IN ('reservation_charge','reservation_refund','reservation_reschedule')),0) AS account_net,
            EXISTS(SELECT 1 FROM member_account_transaction mt WHERE mt.reservation_id=r.id AND mt.user_id=r.user_id
                AND mt.transaction_type='reservation_charge' AND mt.balance_change_cents<0
                AND mt.balance_after_cents-mt.balance_before_cents=mt.balance_change_cents) AS account_evidence
            FROM reservation r JOIN reservation_order ro ON ro.reservation_id=r.id
            WHERE r.reserve_date BETWEEN %s AND %s''',(start,end))
        rows=await cursor.fetchall()
    mismatches=unverified=0
    for row in rows:
        if not row['payment_count'] and not row['account_evidence'] and (row['status']=='paid' or row['paid_at']):
            unverified+=1;continue
        net=int(row['payment_net'] if row['payment_count'] else row['account_net'])
        expected=int(row['amount_cents']) if row['status']=='paid' else 0
        mismatches+=net!=expected or (row['status']=='paid' and row['amount_cents']!=row['payable_amount_cents'])
    return {'orders':len(rows),'mismatches':mismatches,'unverified':unverified}
