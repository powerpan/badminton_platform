import asyncio
import re
from datetime import date, datetime, timedelta

from repositories import booking_operations_repository as operations, court_repository, member_repository, reservation_repository
from services import court_service
from services.config_service import get_reservation_rules
from services.reservation_service import _normalize_reservation, refresh_reservation_statuses
from utils.booking_operations import window, price, at, rank_windows
from utils.response import ApiError
from utils.time_slots import overlaps


def date_range(start, end):
    try:
        first = date.fromisoformat(str(start))
        last = date.fromisoformat(str(end))
    except (ValueError, TypeError) as exc:
        raise ApiError(400, '日期格式应为 YYYY-MM-DD', 400) from exc
    if not 0 <= (last - first).days <= 365:
        raise ApiError(400, '日期范围应为 1 至 366 天', 400)
    return first, last


async def blocks(settings, start, end, court_id=None):
    first, last = date_range(start, end)
    rows = await operations.list_blocks(settings, first, last, court_id)
    return {'items': [_normalize_reservation(row) for row in rows]}


async def create_block(settings, body, actor):
    # Blocks may cover a whole business day, beyond a normal reservation's maximum.
    from dataclasses import replace
    rules = replace(await get_reservation_rules(settings), max_reservation_hours=24)
    target = window(body, rules)
    reason = str(body.get('reason') or '').strip()
    if not 2 <= len(reason) <= 255:
        raise ApiError(400, '请填写 2 至 255 字的维护或包场原因', 400)
    await refresh_reservation_statuses(settings)
    return {'id': await operations.create_block(settings, target, reason, actor)}


async def detail(settings, reservation_id, actor):
    row = await reservation_repository.get_reservation_detail(settings, reservation_id)
    if not row or row['user_id'] != actor['id']:
        raise ApiError(404, '预约不存在', 404)
    return row


async def quote(settings, reservation_id, body, actor):
    await refresh_reservation_statuses(settings)
    rules = await get_reservation_rules(settings)
    target = window(body, rules)
    row = await detail(settings, reservation_id, actor)
    if row['status'] != 'confirmed' or at(row['reserve_date'], row['start_time']) <= datetime.now() or row.get('attendance_outcome'):
        raise ApiError(409, '只有尚未开始且未核销的已支付预约可以改期', 409)
    if row['court_id'] == target['court_id'] and all(at(row['reserve_date'], row[k]) == at(target['reserve_date'], target[k]) for k in ('start_time', 'end_time')):
        raise ApiError(400, '新场次与原场次相同', 400)
    court = await court_repository.get_court_by_id(settings, target['court_id'])
    if not court or court['status'] != 1:
        raise ApiError(409, '目标场地不可用', 409)
    rows = await reservation_repository.list_reservations_for_court_date(settings, court_id=target['court_id'], reserve_date=target['reserve_date'])
    if any(r['id'] != reservation_id and overlaps(target['start_time'],target['end_time'],r['start_time'],r['end_time']) for r in rows):
        raise ApiError(409, '目标时段已有预约，请换一个时间', 409)
    blocked = await operations.list_blocks(settings,target['reserve_date'],target['reserve_date'],target['court_id'])
    if any(r['status']=='active' and overlaps(target['start_time'],target['end_time'],r['start_time'],r['end_time']) for r in blocked):
        raise ApiError(409, '目标时段因维护或包场暂停预约', 409)
    account = await member_repository.get_member_account(settings, actor['id'])
    cost = price(court, account or {}, target)
    return {'target': {**target, 'start_time': body['start_time'], 'end_time': body['end_time']}, **cost,
            'revision': row.get('revision', 0), 'old_amount_cents': row['payable_amount_cents'],
            'difference_cents': cost['payable_amount_cents'] - row['payable_amount_cents'],
            'court_name': court['court_name']}


async def reschedule(settings, reservation_id, body, actor):
    rules = await get_reservation_rules(settings)
    target = window(body, rules)
    key = str(body.get('request_key') or '')
    if not re.fullmatch(r'[A-Za-z0-9_-]{16,64}', key):
        raise ApiError(400, '改期请求号不合法', 400)
    try:
        revision, amount = int(body['expected_revision']), int(body['expected_amount_cents'])
        if revision < 0 or amount < 0: raise ValueError()
    except (ValueError, KeyError, TypeError) as exc:
        raise ApiError(400, '请先获取改期报价', 400) from exc
    await refresh_reservation_statuses(settings)
    await operations.reschedule(settings, reservation_id=reservation_id, actor=actor, target=target,
        daily_limit=rules.daily_reservation_limit, expected_revision=revision, expected_amount=amount, request_key=key)
    return _normalize_reservation(await detail(settings, reservation_id, actor))


async def recommendations(settings, body, actor):
    rules = await get_reservation_rules(settings)
    try:
        day = date.fromisoformat(str(body['reserve_date']))
        earliest = datetime.strptime(str(body['earliest_time']), '%H:%M').time()
        duration = int(body['duration_minutes'])
        preferred = int(body['preferred_court_id']) if body.get('preferred_court_id') else None
    except (ValueError, KeyError, TypeError) as exc:
        raise ApiError(400, '请填写日期、最早时间和时长', 400) from exc
    if not date.today() <= day <= date.today() + timedelta(days=rules.advance_reservation_days):
        raise ApiError(400, '日期不在可预约范围', 400)
    if duration <= 0 or duration % rules.slot_interval_minutes or duration > rules.max_reservation_hours * 60:
        raise ApiError(400, '时长应为时间格的整数倍，且不超过最长预约时长', 400)
    courts = await court_repository.list_courts(settings, status=1, offset=0, limit=10000)
    if preferred and not any(c['id'] == preferred for c in courts):
        raise ApiError(400, '偏好场地不可用', 400)
    account = await member_repository.get_member_account(settings, actor['id'])
    # Bound DB concurrency to the pool size; each response is a fresh snapshot.
    await refresh_reservation_statuses(settings)
    semaphore = asyncio.Semaphore(4)
    async def slots(court):
        async with semaphore:
            return court['id'], (await court_service.get_slots(settings, court_id=court['id'], date_arg=str(day), refresh=False))['slots']
    slot_map = dict(await asyncio.gather(*(slots(c) for c in courts)))
    items = rank_windows(courts, slot_map, day=day, earliest=earliest, duration=duration,
                         interval=rules.slot_interval_minutes, account=account or {}, preferred=preferred)
    return {'items': items, 'generated_at': datetime.now().astimezone().isoformat(), 'strategy': 'earliest-preference-price-v1'}
