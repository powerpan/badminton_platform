from handlers.base import BaseHandler
from services import community_service
from utils.query import pagination
from utils.response import success


class CommunityPostsHandler(BaseHandler):
    async def get(self) -> None:
        settings = self.application.settings["app_settings"]
        page, page_size, offset = pagination(self)
        data = await community_service.list_public_posts(settings, page=page, page_size=page_size, offset=offset)
        self.write_json(success(data))

    async def post(self) -> None:
        settings = self.application.settings["app_settings"]
        current_user = await self.require_customer()
        post = await community_service.create_post(settings, current_user=current_user, body=self.get_json_body())
        self.write_json(success(post, "动态已发布"))


class CommunityPostHideHandler(BaseHandler):
    async def put(self, post_id: str) -> None:
        settings = self.application.settings["app_settings"]
        current_user = await self.require_customer()
        post = await community_service.hide_own_post(
            settings,
            current_user=current_user,
            post_id=self.path_int(post_id, "动态ID"),
        )
        self.write_json(success(post, "动态已隐藏"))
