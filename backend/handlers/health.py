from datetime import datetime

from handlers.base import BaseHandler
from services.health_service import collect_health
from utils.response import success


class HealthHandler(BaseHandler):
    async def get(self) -> None:
        if self.request.path.startswith("/api/admin/"):
            await self.require_admin()

        settings = self.application.settings["app_settings"]
        health = await collect_health(settings)
        health["checked_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.write_json(success(health))
