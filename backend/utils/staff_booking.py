"""Whole-slot walk-in rules, with no membership or wallet side effects."""
import hashlib
import json
import re
from datetime import datetime, time, timedelta, timezone

from utils.booking_operations import at, minutes
from utils.response import ApiError


def request_key(body):
    key = body.get('request_key')
    if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{8,64}', key):
        raise ApiError(400, '请求号须为 8–64 位字母、数字或 _ . : -', 400)
    return key


def digest(body):
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def text_field(body, field, maximum=50):
    value = body.get(field) or ''
    if not isinstance(value, str) or len(value.strip()) > maximum:
        raise ApiError(400, f'{field} 格式或长度不合法', 400)
    return value.strip() or None


def parse_target(body):
    try:
        if type(body['court_id']) is not int or body['court_id'] <= 0:
            raise ValueError()
        return {'court_id': body['court_id'],
                'reserve_date': datetime.strptime(str(body['reserve_date']), '%Y-%m-%d').date(),
                'start_time': datetime.strptime(str(body['start_time']), '%H:%M').time(),
                'end_time': datetime.strptime(str(body['end_time']), '%H:%M').time()}
    except (KeyError, ValueError, TypeError) as exc:
        raise ApiError(400, '请提供有效场地、日期及 HH:MM 起止时间', 400) from exc


def validate_window(target, rules, now, *, extension=False):
    start, end = (at(target['reserve_date'], target[k]) for k in ('start_time', 'end_time'))
    duration = minutes(target['end_time']) - minutes(target['start_time'])
    opening, closing = (at(target['reserve_date'], t) for t in (rules.business_start_time, rules.business_end_time))
    interval = rules.slot_interval_minutes
    if not 0 < duration <= rules.max_reservation_hours * 60 or start < opening or end > closing:
        raise ApiError(400, '请选择营业时间内、未超过时长限制的整段场次', 400)
    if any((minutes(target[k]) - minutes(rules.business_start_time)) % interval for k in ('start_time', 'end_time')):
        raise ApiError(400, '请选择系统时间段的边界', 400)
    if extension:
        if start <= now:
            raise ApiError(409, '续场时段已开始，请刷新原单', 409)
        deadline = start
    else:
        deadline = start + timedelta(minutes=interval)
        if not start <= now < deadline:
            raise ApiError(409, '到店开场须从当前所在时间段开始，请刷新排期', 409)
    return min(now + timedelta(minutes=rules.reservation_payment_timeout_minutes), deadline)


def original_price(court, target):
    duration = minutes(target['end_time']) - minutes(target['start_time'])
    amount = int(court['price_per_hour_cents']) * duration // 60
    if not 0 <= amount <= 2_147_483_647:
        raise ApiError(400, '场地金额超出允许范围', 400)
    return {'price_per_hour_cents': int(court['price_per_hour_cents']), 'duration_minutes': duration,
            'original_amount_cents': amount, 'payable_amount_cents': amount,
            'discount_amount_cents': 0, 'discount_rate': 100,
            'member_level_snapshot': 'normal', 'points_awarded': 0}


def json_value(value):
    if isinstance(value, dict): return {k: json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)): return [json_value(v) for v in value]
    if isinstance(value, datetime): return value.replace(tzinfo=timezone(timedelta(hours=8))).isoformat()
    if isinstance(value, time): return value.strftime('%H:%M')
    if isinstance(value, timedelta): return f'{minutes(value)//60:02d}:{minutes(value)%60:02d}'
    if hasattr(value, 'isoformat'): return value.isoformat()
    return value
