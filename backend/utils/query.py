from typing import Any

from utils.response import ApiError


def to_int(value: Any, default: int, *, min_value: int | None = None, max_value: int | None = None) -> int:
    if value is None or value == "":
        result = default
    else:
        try:
            result = int(value)
        except (TypeError, ValueError) as exc:
            raise ApiError(400, "数字参数格式错误", 400) from exc
    if min_value is not None and result < min_value:
        result = min_value
    if max_value is not None and result > max_value:
        result = max_value
    return result


def pagination(handler: Any) -> tuple[int, int, int]:
    page = to_int(handler.get_argument("page", None), 1, min_value=1)
    page_size = to_int(handler.get_argument("page_size", None), 10, min_value=1, max_value=100)
    offset = (page - 1) * page_size
    return page, page_size, offset


def clean_text(value: Any, default: str = "") -> str:
    text = str(value if value is not None else default).strip()
    return text
