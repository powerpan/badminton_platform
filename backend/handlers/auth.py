from handlers.base import BaseHandler
from services import auth_service, captcha_service
from utils.response import success


class CaptchaHandler(BaseHandler):
    async def get(self) -> None:
        settings = self.application.settings["app_settings"]
        self.write_json(success(await captcha_service.create_captcha(settings)))


class RegisterHandler(BaseHandler):
    async def post(self) -> None:
        settings = self.application.settings["app_settings"]
        user = await auth_service.register(settings, self.get_json_body())
        self.write_json(success(user))


class LoginHandler(BaseHandler):
    async def post(self) -> None:
        settings = self.application.settings["app_settings"]
        login_result = await auth_service.login(settings, self.get_json_body())
        self.write_json(success(login_result))


class RefreshHandler(BaseHandler):
    async def post(self) -> None:
        settings = self.application.settings["app_settings"]
        login_result = await auth_service.refresh_login(settings, self.get_json_body())
        self.write_json(success(login_result))


class LogoutHandler(BaseHandler):
    async def post(self) -> None:
        settings = self.application.settings["app_settings"]
        await auth_service.logout(settings, self.get_json_body())
        self.write_json(success(None, "已退出登录"))


class ProfileHandler(BaseHandler):
    async def get(self) -> None:
        user = await self.require_current_user()
        self.write_json(success(await auth_service.public_current_user(user)))

    async def put(self) -> None:
        settings = self.application.settings["app_settings"]
        user = await self.require_current_user()
        updated_user = await auth_service.update_profile(settings, user, self.get_json_body())
        self.write_json(success(updated_user))


class PasswordHandler(BaseHandler):
    async def put(self) -> None:
        settings = self.application.settings["app_settings"]
        user = await self.require_current_user()
        await auth_service.change_password(settings, user, self.get_json_body())
        self.write_json(success(None, "密码修改成功"))
