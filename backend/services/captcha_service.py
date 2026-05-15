import base64
import html
import secrets
import uuid
from typing import Any

from config.settings import Settings
from services import redis_service
from utils.response import ApiError


CAPTCHA_CHARS = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"


def _captcha_key(captcha_id: str) -> str:
    return f"auth:captcha:{captcha_id}"


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _generate_code(length: int = 4) -> str:
    return "".join(secrets.choice(CAPTCHA_CHARS) for _ in range(length))


def _svg_data_url(code: str) -> str:
    safe_code = html.escape(code)
    line_1_y = secrets.randbelow(44) + 18
    line_2_y = secrets.randbelow(44) + 18
    text_dx = " ".join(str(secrets.randbelow(5) - 2) for _ in code)
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="132" height="46" viewBox="0 0 132 46">
  <rect width="132" height="46" rx="6" fill="#f8fafc"/>
  <path d="M8 {line_1_y} C38 4, 74 52, 124 {line_2_y}" fill="none" stroke="#9bd8b7" stroke-width="2"/>
  <path d="M6 {line_2_y} C42 48, 78 2, 126 {line_1_y}" fill="none" stroke="#cbd5e1" stroke-width="1.5"/>
  <text x="18" y="31" dx="{text_dx}" fill="#133428" font-family="Arial, sans-serif" font-size="24" font-weight="700" letter-spacing="4">{safe_code}</text>
</svg>"""
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


async def create_captcha(settings: Settings) -> dict[str, Any]:
    captcha_id = uuid.uuid4().hex
    code = _generate_code()
    await redis_service.set_value(settings, _captcha_key(captcha_id), code, settings.captcha_expire_seconds)
    return {
        "captcha_id": captcha_id,
        "image_data": _svg_data_url(code),
        "expires_in": settings.captcha_expire_seconds,
    }


async def verify_captcha(settings: Settings, captcha_id: Any, captcha_code: Any) -> None:
    captcha_id_text = _clean_text(captcha_id)
    captcha_code_text = _clean_text(captcha_code).upper()
    if not captcha_id_text or not captcha_code_text:
        raise ApiError(400, "请输入验证码", 400)

    key = _captcha_key(captcha_id_text)
    stored_code = await redis_service.get_value(settings, key)
    if stored_code is None:
        raise ApiError(400, "验证码已过期，请刷新后重试", 400)

    await redis_service.delete_keys(settings, key)
    if stored_code.upper() != captcha_code_text:
        raise ApiError(400, "验证码错误，请刷新后重试", 400)
