import asyncio
import logging

from tornado.ioloop import PeriodicCallback

from config.settings import Settings
from services.reservation_service import refresh_reservation_statuses


class ReservationMaintenance:
    """Idempotent database cleanup, also safe when multiple app workers run it."""

    def __init__(self, settings: Settings, interval_ms: int = 30_000) -> None:
        self.settings = settings
        self._task: asyncio.Task | None = None
        self._periodic = PeriodicCallback(self.run, interval_ms)

    def start(self) -> None:
        self._periodic.start()

    async def run(self) -> None:
        if self._task is not None:
            return
        self._task = asyncio.current_task()
        try:
            await refresh_reservation_statuses(self.settings)
        except Exception:
            logging.exception("Reservation maintenance failed; retrying on next interval")
        finally:
            self._task = None

    async def stop(self) -> None:
        self._periodic.stop()
        if self._task is not None:
            await self._task
