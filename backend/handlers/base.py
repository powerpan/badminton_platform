import json
from typing import Any

import tornado.web

from repositories import user_repository
from utils.response import ApiError, error
from utils.tokens import decode_access_token


class BaseHandler(tornado.web.RequestHandler):
    _current_user_data: dict[str, Any] | None = None

    def set_default_headers(self) -> None:
        self.set_header("Content-Type", "application/json; charset=UTF-8")
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Headers", "Authorization,Content-Type")
        self.set_header("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS")

    def options(self, *_args: Any, **_kwargs: Any) -> None:
        self.set_status(204)
        self.finish()

    def write_json(self, payload: dict[str, Any], status_code: int = 200) -> None:
        self.set_status(status_code)
        self.finish(json.dumps(payload, ensure_ascii=False))

    def get_json_body(self) -> dict[str, Any]:
        if not self.request.body:
            return {}
        try:
            body = json.loads(self.request.body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ApiError(400, "请求体不是合法 JSON", 400) from exc
        if not isinstance(body, dict):
            raise ApiError(400, "请求体必须是 JSON 对象", 400)
        return body

    async def require_current_user(self) -> dict[str, Any]:
        if self._current_user_data is not None:
            return self._current_user_data

        auth_header = self.request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise ApiError(401, "请先登录", 401)

        token = auth_header.removeprefix("Bearer ").strip()
        if not token:
            raise ApiError(401, "请先登录", 401)

        settings = self.application.settings["app_settings"]
        payload = decode_access_token(token, settings.jwt_secret)
        user = await user_repository.get_user_by_id(settings, payload["user_id"])
        if user is None:
            raise ApiError(401, "登录用户不存在，请重新登录", 401)
        if user["status"] != 1:
            raise ApiError(403, "账号已被禁用", 403)

        self._current_user_data = user
        return user

    async def require_admin(self) -> dict[str, Any]:
        user = await self.require_current_user()
        if user["role"] != "admin":
            raise ApiError(403, "无管理员权限", 403)
        return user

    def write_error(self, status_code: int, **kwargs: Any) -> None:
        exc_info = kwargs.get("exc_info")
        if exc_info and isinstance(exc_info[1], ApiError):
            api_error = exc_info[1]
            self.write_json(error(api_error.code, api_error.message), api_error.status_code)
            return
        self.write_json(error(status_code, "系统内部错误" if status_code >= 500 else "请求失败"), status_code)
