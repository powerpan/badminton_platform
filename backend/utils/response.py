from typing import Any, Optional

import tornado.web


def success(data: Any = None, message: str = "success") -> dict[str, Any]:
    return {
        "code": 0,
        "message": message,
        "data": data,
    }


def error(code: int, message: str, data: Optional[Any] = None) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "data": data,
    }


class ApiError(tornado.web.HTTPError):
    def __init__(self, code: int, message: str, status_code: int = 400) -> None:
        super().__init__(status_code=status_code, log_message=message)
        self.code = code
        self.message = message
