from datetime import datetime, timedelta
from repositories.database import fetch_all
from repositories.finance_repository import booking_reconciliation
from services.booking_operations_service import date_range
from services.reservation_service import refresh_reservation_statuses
from utils.booking_operations import minutes, at


def aggregate(rows, ledger, start, end, now=None):
    now = now or datetime.now()
    daily = {str(start+timedelta(days=i)): {'date': str(start+timedelta(days=i)), 'total': 0, 'active': 0, 'canceled': 0, 'booked_minutes': 0}
             for i in range((end-start).days+1)}
    hourly = {hour: 0 for hour in range(24)}
    ended, checked, absent = 0, 0, 0
    for row in rows:
        day = daily[str(row['reserve_date'])]
        day['total'] += 1
        day['canceled'] += row['status'] == 'canceled'
        if row['status'] in ('pending','confirmed','completed'):
            first, last = minutes(row['start_time']), minutes(row['end_time'])
            day['active'] += 1
            day['booked_minutes'] += last - first
            for hour in range(24):
                hourly[hour] += max(0, min(last, (hour+1)*60)-max(first,hour*60))
        if row.get('source') != 'walk_in_extension' and row['status'] in ('confirmed','completed') and at(row['reserve_date'],row['end_time']) <= now:
            ended += 1
            checked += row.get('attendance_outcome') == 'checked_in'
            absent += row.get('attendance_outcome') == 'no_show'
    total = len(rows)
    canceled = sum(day['canceled'] for day in daily.values())
    # This legacy panel reports wallet movement only; channel receipts have a separate financial view.
    charges = sum(max(0,-int(row['balance_change_cents'])) for row in ledger)
    refunds = sum(max(0,int(row['balance_change_cents'])) for row in ledger)
    known = checked + absent
    return {'daily': list(daily.values()), 'hourly': [{'hour': h, 'label': f'{h:02}:00–{h+1:02}:00', 'booked_minutes': value} for h,value in hourly.items()],
            'total': total, 'canceled': canceled, 'cancellation_rate': round(canceled/total*100,2) if total else None,
            'ended': ended, 'checked_in': checked, 'no_show': absent, 'unrecorded': ended-known,
            'attendance_rate': round(checked/known*100,2) if known else None,
            'attendance_coverage': round(known/ended*100,2) if ended else None,
            'charges_cents': charges, 'refunds_cents': refunds, 'net_cents': charges-refunds,
            'ledger_count': len(ledger)}


async def report(settings, start_arg, end_arg):
    start, end = date_range(start_arg, end_arg)
    await refresh_reservation_statuses(settings)
    rows = await fetch_all(settings, '''SELECT r.reserve_date,r.start_time,r.end_time,r.status,r.source,a.outcome AS attendance_outcome
        FROM reservation r LEFT JOIN reservation_attendance a ON a.reservation_id=r.id
        WHERE r.reserve_date BETWEEN %s AND %s''', (start,end))
    ledger = await fetch_all(settings, '''SELECT balance_change_cents FROM member_account_transaction
        WHERE created_at >= %s AND created_at < %s
        AND transaction_type IN ('reservation_charge','reservation_refund','reservation_reschedule')''', (start,end+timedelta(days=1)))
    result = aggregate(rows,ledger,start,end)
    result['reconciliation'] = await booking_reconciliation(settings,start,end)
    result.update(date_from=str(start), date_to=str(end), generated_at=datetime.now().astimezone().isoformat())
    return result
