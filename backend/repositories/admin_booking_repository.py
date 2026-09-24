"""Administrator booking search and evidence, read from one database snapshot."""
import json

from repositories.transaction import transaction
from repositories.reservation_repository import RESERVATION_MONEY_COLUMNS, RESERVATION_ORDER_COLUMNS
from utils.response import ApiError
from utils.staff_booking import json_value


FROM_SQL = ''' FROM reservation r
    LEFT JOIN user u ON u.id=r.user_id
    JOIN court c ON c.id=r.court_id
    LEFT JOIN reservation_order ro ON ro.reservation_id=r.id
    LEFT JOIN user creator ON creator.id=r.operator_id '''
SELECT_SQL = f'''SELECT r.id,r.reservation_no,r.user_id,u.username,u.nickname,u.contact AS customer_contact,
    r.court_id,c.court_no,c.court_name,r.reserve_date,r.start_time,r.end_time,r.time_slot,
    r.status,r.remark,{RESERVATION_MONEY_COLUMNS},{RESERVATION_ORDER_COLUMNS},
    r.created_at,r.updated_at,r.canceled_at ''' + FROM_SQL


def contains(value):
    # Use an explicit escape character, independent of backslash SQL modes.
    return '%' + value.replace('!', '!!').replace('%', '!%').replace('_', '!_') + '%'


def conditions(filters):
    where, args = [], []
    for key, column in (('status','r.status'),('source','r.source'),('court_id','r.court_id')):
        if filters.get(key) is not None:
            where.append(f'{column}=%s'); args.append(filters[key])
    for key, op in (('date_from','>='),('date_to','<=')):
        if filters.get(key):
            where.append(f'r.reserve_date{op}%s'); args.append(filters[key])
    for key, fields in (
        ('username',('u.username','u.nickname','u.contact','r.guest_name','r.guest_contact')),
        ('operator',('r.operator_name_snapshot','creator.username','creator.nickname')),
    ):
        if filters.get(key):
            where.append('(' + ' OR '.join(f"{field} LIKE %s ESCAPE '!'" for field in fields) + ')')
            args.extend([contains(filters[key])] * len(fields))
    if filters.get('pay_method'):
        where.append('''(ro.pay_method=%s OR EXISTS (SELECT 1 FROM payment_order p
            WHERE p.reservation_order_id=ro.id AND p.pay_method=%s))''')
        args.extend([filters['pay_method']] * 2)
    if filters.get('order_no'):
        where.append('''(r.reservation_no=%s OR ro.order_no=%s OR EXISTS (
            SELECT 1 FROM payment_order p LEFT JOIN payment_refund rf ON rf.payment_order_id=p.id
            WHERE p.reservation_order_id=ro.id AND (p.payment_no=%s OR rf.refund_no=%s)))''')
        args.extend([filters['order_no']] * 4)
    return (' WHERE ' + ' AND '.join(where) if where else ''), args


async def list_page(settings, filters, *, page, page_size):
    where, args = conditions(filters)
    async with transaction(settings, read_only=True) as cursor:
        await cursor.execute('SELECT NOW() AS server_now')
        now = (await cursor.fetchone())['server_now']
        await cursor.execute('SELECT COUNT(*) AS total' + FROM_SQL + where, args)
        total = (await cursor.fetchone())['total']
        await cursor.execute(SELECT_SQL + where +
            ' ORDER BY r.reserve_date DESC,r.start_time DESC,r.id DESC LIMIT %s OFFSET %s',
            (*args,page_size,(page-1)*page_size))
        items = list(await cursor.fetchall())
    return json_value({'items':items,'total':total,'page':page,'page_size':page_size,'server_now':now})


async def detail(settings, reservation_id):
    async with transaction(settings, read_only=True) as cursor:
        await cursor.execute('SELECT NOW() AS server_now')
        now = (await cursor.fetchone())['server_now']
        await cursor.execute(SELECT_SQL + ' WHERE r.id=%s', (reservation_id,))
        row = await cursor.fetchone()
        if not row:
            raise ApiError(404,'预约记录不存在',404)
        root_id = row['root_reservation_id'] or row['id']
        await cursor.execute('''SELECT r.id,r.reservation_no,r.parent_reservation_id,r.source,r.reserve_date,
            r.start_time,r.end_time,r.status,r.payable_amount_cents,c.court_no,c.court_name
            FROM reservation r JOIN court c ON c.id=r.court_id
            WHERE r.id=%s OR r.root_reservation_id=%s
            ORDER BY r.reserve_date,r.start_time,r.id''',(root_id,root_id))
        row['chain'] = list(await cursor.fetchall())
        await cursor.execute('''SELECT p.id,p.payment_no,p.purpose,p.amount_cents,p.pay_method,p.status,
            p.created_at,p.expires_at,p.paid_at,p.closed_at,p.operator_id,p.operator_name_snapshot,
            collected.operator_id AS collected_by,collected.created_at AS collection_recorded_at,
            actor.username AS collector_username,
            COALESCE((SELECT SUM(amount_cents) FROM payment_refund rf
                WHERE rf.payment_order_id=p.id AND rf.status='succeeded'),0) AS refunded_cents
            FROM payment_order p
            LEFT JOIN payment_command collected ON collected.id=(SELECT MIN(pc.id) FROM payment_command pc
                WHERE pc.payment_order_id=p.id AND pc.action IN ('mock_confirm','balance_pay')
                AND p.paid_at IS NOT NULL)
            LEFT JOIN user actor ON actor.id=collected.operator_id
            WHERE p.reservation_order_id=%s ORDER BY p.created_at,p.id''',(row['order_id'],))
        row['payments'] = list(await cursor.fetchall())
        for payment in row['payments']:
            payment['refunded_cents'] = int(payment['refunded_cents'])
        await cursor.execute('''SELECT rf.id,rf.refund_no,rf.payment_order_id,p.payment_no,p.pay_method,
            rf.refund_group_no,rf.amount_cents,rf.reason,rf.purpose,rf.status,rf.operator_id,
            rf.operator_name_snapshot,rf.refunded_at FROM payment_refund rf
            JOIN payment_order p ON p.id=rf.payment_order_id WHERE p.reservation_order_id=%s
            ORDER BY rf.refunded_at,rf.id''',(row['order_id'],))
        row['refunds'] = list(await cursor.fetchall())
        await cursor.execute('''SELECT id,transaction_type,balance_change_cents,balance_before_cents,
            balance_after_cents,points_change,points_before,points_after,reason,operator_id,operator_username,
            payment_order_id,payment_refund_id,created_at FROM member_account_transaction
            WHERE reservation_id=%s ORDER BY created_at,id''',(reservation_id,))
        row['account_transactions'] = list(await cursor.fetchall())
        await cursor.execute('''SELECT ch.id,ch.before_snapshot,ch.after_snapshot,ch.balance_change_cents,
            ch.points_change,ch.changed_by,ch.pay_method,ch.settlement_delta_cents,ch.payment_order_id,
            ch.refund_group_no,ch.created_at,actor.username AS operator_username
            FROM reservation_change ch LEFT JOIN user actor ON actor.id=ch.changed_by
            WHERE ch.reservation_id=%s ORDER BY ch.id''',(reservation_id,))
        row['changes'] = list(await cursor.fetchall())
        for change in row['changes']:
            for field in ('before_snapshot','after_snapshot'):
                change[field] = json.loads(change[field])
        court_ids = sorted({change[field]['court_id'] for change in row['changes']
            for field in ('before_snapshot','after_snapshot')})
        if court_ids:
            await cursor.execute('SELECT id,court_no,court_name FROM court WHERE id IN (' +
                ','.join(['%s'] * len(court_ids)) + ')', court_ids)
            courts = {court['id']:court for court in await cursor.fetchall()}
            for change in row['changes']:
                for field in ('before_snapshot','after_snapshot'):
                    snapshot = change[field]
                    court = courts.get(snapshot['court_id'], {})
                    snapshot['court_no'] = court.get('court_no')
                    snapshot['court_name'] = court.get('court_name')
        row['server_now'] = now
    return json_value(row)
