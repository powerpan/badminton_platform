import re
import base64
import qrcode
from qrcode.image.svg import SvgPathFillImage
from repositories import shop_checkout_repository as repository
from utils.staff_booking import request_key
from utils.response import ApiError


def normalize_code(body):
    value = body.get('code')
    if not isinstance(value, str) or len(value) > 64:
        raise ApiError(400, '请填写有效取货码', 400)
    value = value.strip().upper().removeprefix('BF-PICKUP:')
    value = value.replace('-', '').replace(' ', '')
    if not re.fullmatch(r'[2-9A-HJKMNP-Z]{12}', value):
        raise ApiError(400, '请填写完整的12位取货码', 400)
    return value


async def get_code(settings, actor, order_id):
    result = await repository.pickup_code(settings, actor, order_id)
    if result['qr_content']:
        image = qrcode.make(result['qr_content'], image_factory=SvgPathFillImage, box_size=8, border=4)
        result['qr_data_url'] = 'data:image/svg+xml;base64,' + base64.b64encode(image.to_string()).decode('ascii')
    else:
        result['qr_data_url'] = None
    return result


async def lookup(settings, actor, body):
    return await repository.pickup_lookup(settings, actor, normalize_code(body))


async def redeem(settings, actor, body):
    code = normalize_code(body)
    order = await repository.pickup_lookup(settings, actor, code)
    return await repository.action(settings, actor, order['id'], 'redeem', request_key(body), code=code)
