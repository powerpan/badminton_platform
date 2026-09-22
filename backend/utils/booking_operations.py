"""Pure rules shared by quotes, transactions and algorithm tests."""
from datetime import datetime, time, timedelta
from utils.response import ApiError
from utils.member_levels import effective_member_level, discount_rate_for_level


def minutes(value):
    if isinstance(value, timedelta):
        return int(value.total_seconds() // 60)
    if isinstance(value, time):
        return value.hour * 60 + value.minute
    parts = str(value).split(':')
    return int(parts[0]) * 60 + int(parts[1])


def at(day, value):
    return datetime.combine(day, time()) + timedelta(minutes=minutes(value))


def window(body, rules, now=None):
    now = now or datetime.now()
    try:
        day = datetime.strptime(str(body['reserve_date']), '%Y-%m-%d').date()
        start = datetime.strptime(str(body['start_time']), '%H:%M').time()
        end = datetime.strptime(str(body['end_time']), '%H:%M').time()
        court_id = int(body['court_id'])
    except (ValueError, TypeError, KeyError) as exc:
        raise ApiError(400, '请提供有效场地、日期及 HH:MM 起止时间', 400) from exc
    duration = minutes(end) - minutes(start)
    if court_id <= 0 or duration <= 0 or at(day, start) <= now:
        raise ApiError(400, '请选择尚未开始的有效时段', 400)
    if day > now.date() + timedelta(days=rules.advance_reservation_days):
        raise ApiError(400, '预约日期超过可提前预约范围', 400)
    if start < rules.business_start_time or end > rules.business_end_time:
        raise ApiError(400, '预约时间不在营业时间内', 400)
    if any((minutes(t) - minutes(rules.business_start_time)) % rules.slot_interval_minutes for t in (start, end)):
        raise ApiError(400, '请选择系统时间段的边界', 400)
    if duration > rules.max_reservation_hours * 60:
        raise ApiError(400, '预约时长超过系统限制', 400)
    return {'court_id': court_id, 'reserve_date': day, 'start_time': start, 'end_time': end}


def price(court, account, target):
    duration = minutes(target['end_time']) - minutes(target['start_time'])
    level = effective_member_level(account.get('member_level'), account.get('expires_at'), target['reserve_date'])
    rate = discount_rate_for_level(level)
    original = int(court['price_per_hour_cents']) * duration // 60
    payable = original * rate // 100
    return {'price_per_hour_cents': int(court['price_per_hour_cents']), 'duration_minutes': duration,
            'member_level_snapshot': level, 'discount_rate': rate,
            'original_amount_cents': original, 'discount_amount_cents': original - payable,
            'payable_amount_cents': payable, 'points_awarded': payable // 100}


def validate_attendance(reservation, outcome, now=None):
    now = now or datetime.now()
    if outcome not in ('checked_in', 'no_show'):
        raise ApiError(400, '到场结论不合法', 400)
    if reservation['status'] not in ('confirmed', 'completed'):
        raise ApiError(409, '只有已确认或已结束预约可以记录到场', 409)
    start, end = (at(reservation['reserve_date'], reservation[k]) for k in ('start_time', 'end_time'))
    if outcome == 'checked_in' and not start - timedelta(minutes=30) <= now < end:
        raise ApiError(409, '核销时间为开场前 30 分钟至场次结束前', 409)
    if outcome == 'no_show' and now < end:
        raise ApiError(409, '场次结束后才能确认未到场', 409)


def rank_windows(courts, slot_map, *, day, earliest, duration, interval, account, preferred=None, limit=3):
    """Prefix sums: O(courts * slots), followed by deterministic candidate sorting."""
    size = duration // interval
    candidates = []
    for court in courts:
        slots = slot_map.get(court['id'], [])
        prefix = [0]
        for slot in slots:
            prefix.append(prefix[-1] + (slot['status'] != 'available'))
        for i in range(len(slots) - size + 1):
            last = i + size
            start, end = slots[i]['start_time'], slots[last-1]['end_time']
            if minutes(start) < minutes(earliest) or prefix[last] != prefix[i]:
                continue
            if minutes(end) - minutes(start) != duration:
                continue
            cost = price(court, account, {'reserve_date': day, 'start_time': start, 'end_time': end})
            # Isolated single-slot leftovers are a final tie-break, never a hard rule.
            fragments = int(i > 0 and slots[i-1]['status'] == 'available' and (i == 1 or slots[i-2]['status'] != 'available'))
            fragments += int(last < len(slots) and slots[last]['status'] == 'available' and (last+1 == len(slots) or slots[last+1]['status'] != 'available'))
            key = (minutes(start) - minutes(earliest), int(bool(preferred) and court['id'] != preferred), cost['payable_amount_cents'], fragments, court['court_no'], court['id'])
            reasons = ['最早可用时间' if key[0] == 0 else f"比最早时间晚 {key[0]} 分钟", f'连续 {duration} 分钟']
            if preferred == court['id']:
                reasons.append('符合场地偏好')
            candidates.append((key, {'court_id': court['id'], 'court_name': court['court_name'], 'court_no': court['court_no'],
                'reserve_date': day.isoformat(), 'start_time': start, 'end_time': end, **cost, 'reasons': reasons}))
    candidates.sort(key=lambda row: row[0])
    return [row[1] for row in candidates[:limit]]
