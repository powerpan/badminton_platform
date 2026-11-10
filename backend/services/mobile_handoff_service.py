"""A desktop session approves one phone without putting account tokens in a QR."""
import base64
import hashlib
import ipaddress
import json
import re
import secrets
import time
from urllib.parse import urlsplit

import qrcode
from qrcode.image.svg import SvgPathFillImage

from repositories import shop_repository, user_repository
from services import auth_service, redis_service
from utils.response import ApiError

LIFETIME = 120
RECEIPT_SECONDS = 30
PREFIX = 'auth:mobile-handoff:'
CAS = """
if redis.call('GET', KEYS[1]) ~= ARGV[1] then return 0 end
local ttl = redis.call('PTTL', KEYS[1])
if ttl <= 0 then return 0 end
if tonumber(ARGV[3]) > 0 then ttl = math.min(ttl, tonumber(ARGV[3])) end
redis.call('SET', KEYS[1], ARGV[2], 'PX', ttl)
return 1
"""


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-f0-9]{32}', value):
        raise ApiError(400, '授权请求无效，请重新扫码', 400)
    return value


def secret(body, name):
    value = body.get(name)
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{43,64}', value):
        raise ApiError(400, '授权信息不完整，请重新扫码', 400)
    return digest(value)


def web_origin(settings):
    value = settings.mobile_web_origin.strip().rstrip('/')
    try:
        url = urlsplit(value)
        host = url.hostname or ''
        _ = url.port
        if (url.username or url.password or url.path or url.query or url.fragment or not host
                or host.lower() == 'localhost' or host.endswith('.localhost')
                or any(c.isspace() for c in value) or '\\' in value):
            raise ValueError()
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address and (address.is_loopback or address.is_unspecified or address.is_link_local):
            raise ValueError()
        if url.scheme != 'https' and not (settings.app_env == 'dev' and url.scheme == 'http'
                                         and address and address.is_private):
            raise ValueError()
    except (ValueError, AttributeError):
        raise ApiError(409, '暂未开通手机扫码查看，请在手机登录网站查看订单。', 409)
    return value


async def limit(settings, bucket, maximum):
    count = await redis_service.increment_with_ttl(settings, PREFIX + 'limit:' + bucket, 60)
    if count > maximum:
        raise ApiError(429, '操作过于频繁，请稍后重试', 429)


async def read(settings, request_id):
    key = PREFIX + identifier(request_id)
    raw = await redis_service.get_value(settings, key)
    if not raw:
        raise ApiError(410, '本次授权已过期，请在电脑重新生成二维码', 410)
    state = json.loads(raw)
    if time.time() >= state['expires_at']:
        raise ApiError(410, '本次授权已过期，请在电脑重新生成二维码', 410)
    return key, raw, state


async def change(settings, key, raw, state, receipt=False):
    return bool(await redis_service.get_redis_client(settings).eval(
        CAS, 1, key, raw, encode(state), RECEIPT_SECONDS * 1000 if receipt else 0))


async def eligible(settings, user_id, order_id, password_digest=None):
    user = await user_repository.get_user_by_id(settings, user_id)
    if not user or user['role'] != 'user' or user['status'] != 1:
        raise ApiError(403, '当前账号不能使用手机授权登录', 403)
    if password_digest and not secrets.compare_digest(password_digest, digest(user['password_hash'])):
        raise ApiError(409, '账号登录信息已变更，请重新登录后扫码', 409)
    order = await shop_repository.get_order(settings, order_id)
    if not order or order['user_id'] != user_id:
        raise ApiError(404, '订单不存在', 404)
    if order['status'] != 'paid' or order.get('pickup_status') != 'ready':
        raise ApiError(409, '订单已不是待取货状态，请刷新订单', 409)
    return user


def public(state):
    return {k: state[k] for k in ('id', 'status', 'order_id', 'expires_at', 'pairing_code', 'username', 'user_id')}


def owner(state, actor, token):
    if (actor['role'] != 'user' or actor['id'] != state['user_id']
            or not secrets.compare_digest(state['issuer_digest'], digest(token))):
        raise ApiError(403, '请在生成二维码的电脑页面操作', 403)


async def create(settings, actor, token, body):
    if actor['role'] != 'user':
        raise ApiError(403, '仅普通用户可使用手机授权登录', 403)
    order_id = body.get('order_id')
    if type(order_id) is not int or order_id <= 0:
        raise ApiError(400, '订单编号无效', 400)
    origin = web_origin(settings)
    user = await eligible(settings, actor['id'], order_id)
    await limit(settings, 'create:' + str(actor['id']), 10)
    request_id, ticket = secrets.token_hex(16), secrets.token_urlsafe(32)
    state = dict(id=request_id, status='waiting', order_id=order_id, user_id=user['id'],
                 username=user['username'], issuer_digest=digest(token), ticket_digest=digest(ticket),
                 password_digest=digest(user['password_hash']), device_digest=None, pairing_code=None,
                 expires_at=time.time() + LIFETIME)
    await redis_service.set_value(settings, PREFIX + request_id, encode(state), LIFETIME)
    url = f'{origin}/mobile-handoff/{request_id}#ticket={ticket}'
    qr = qrcode.make(url, image_factory=SvgPathFillImage, box_size=6, border=4)
    return {**public(state), 'qr_data_url': 'data:image/svg+xml;base64,' + base64.b64encode(qr.to_string()).decode(),
            'mobile_url': url}


async def status(settings, actor, token, request_id):
    _, _, state = await read(settings, request_id)
    owner(state, actor, token)
    return public(state)


async def decide(settings, actor, token, request_id, body):
    decision = body.get('decision')
    if decision not in ('approve', 'deny', 'cancel'):
        raise ApiError(400, '请选择允许或拒绝登录', 400)
    for _ in range(8):
        key, raw, state = await read(settings, request_id)
        owner(state, actor, token)
        if decision == 'approve':
            code = body.get('pairing_code')
            if not isinstance(code, str) or not state['pairing_code'] or not secrets.compare_digest(code, state['pairing_code']):
                raise ApiError(409, '请核对手机与电脑上的核对码', 409)
            if state['status'] in ('approved', 'issuing', 'consumed'):
                return public(state)
            if state['status'] != 'claimed':
                raise ApiError(409, '当前授权不能批准，请重新扫码', 409)
            await eligible(settings, state['user_id'], state['order_id'], state['password_digest'])
            state['status'] = 'approved'
        else:
            if state['status'] in ('denied', 'issuing', 'consumed', 'failed'):
                return public(state)
            state['status'] = 'denied'
        if await change(settings, key, raw, state):
            return public(state)
    raise ApiError(409, '授权状态正在变化，请重新查询', 409)


async def claim(settings, request_id, body):
    ticket, device = secret(body, 'ticket'), secret(body, 'device_secret')
    for _ in range(8):
        key, raw, state = await read(settings, request_id)
        if not secrets.compare_digest(ticket, state['ticket_digest']):
            raise ApiError(403, '二维码无效，请重新扫码', 403)
        if state['device_digest'] and not secrets.compare_digest(device, state['device_digest']):
            raise ApiError(409, '此二维码已有其他设备申请，请在电脑重新生成', 409)
        if state['status'] in ('denied', 'failed'):
            raise ApiError(410, '本次授权已结束，请在电脑重新生成二维码', 410)
        await eligible(settings, state['user_id'], state['order_id'], state['password_digest'])
        if state['status'] != 'waiting':
            return public(state)
        state.update(status='claimed', device_digest=device, pairing_code=f'{secrets.randbelow(1000000):06d}')
        if await change(settings, key, raw, state):
            return public(state)
    raise ApiError(409, '设备绑定结果未确认，请重试', 409)


async def exchange(settings, request_id, body):
    device = secret(body, 'device_secret')
    for _ in range(8):
        key, raw, state = await read(settings, request_id)
        if not state['device_digest'] or not secrets.compare_digest(device, state['device_digest']):
            raise ApiError(403, '请使用刚才扫码的手机继续', 403)
        if state['status'] in ('denied', 'failed'):
            raise ApiError(410, '本次登录未获授权，请在电脑重新生成二维码', 410)
        if state['status'] in ('claimed', 'issuing'):
            return public(state)
        user = await eligible(settings, state['user_id'], state['order_id'], state['password_digest'])
        if state['status'] == 'consumed':
            return {**public(state), 'login': state['login']}
        if state['status'] != 'approved':
            raise ApiError(409, '请先在电脑确认登录', 409)
        state['status'] = 'issuing'
        if not await change(settings, key, raw, state):
            continue
        issuing_raw = encode(state)
        refresh_token = None
        try:
            # Only the CAS winner issues a session; retries cannot issue another one.
            user_info = await auth_service.public_current_user(user)
            access, refresh_token = await auth_service.issue_tokens(settings, user)
            await eligible(settings, state['user_id'], state['order_id'], state['password_digest'])
            state.update(status='consumed', login=dict(token=access, access_token=access,
                         refresh_token=refresh_token, user=user_info))
            if not await change(settings, key, issuing_raw, state, receipt=True):
                raise ApiError(410, '授权已到期，请重新扫码', 410)
            return {**public(state), 'login': state['login']}
        except Exception:
            if refresh_token:
                await auth_service.logout(settings, {'refresh_token': refresh_token})
            state.pop('login', None)
            state['status'] = 'failed'
            await change(settings, key, issuing_raw, state)
            raise
    raise ApiError(409, '登录状态正在确认，请重试', 409)
