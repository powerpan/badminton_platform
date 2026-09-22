import logging
import signal

import tornado.ioloop
import tornado.web

from config.settings import load_settings
from routes import build_routes
from repositories.database import close_pool
from services.redis_service import close_redis_clients
from services.maintenance_service import ReservationMaintenance


def make_app() -> tornado.web.Application:
    settings = load_settings()
    return tornado.web.Application(
        build_routes(),
        app_settings=settings,
        debug=settings.app_env == "dev",
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    app = make_app()
    settings = app.settings["app_settings"]
    server = app.listen(settings.app_port)
    maintenance = ReservationMaintenance(settings)
    maintenance.start()
    loop = tornado.ioloop.IOLoop.current()
    shutting_down = False

    async def shutdown() -> None:
        nonlocal shutting_down
        if shutting_down:
            return
        shutting_down = True
        server.stop()
        try:
            await maintenance.stop()
            await server.close_all_connections()
            await close_redis_clients()
            await close_pool()
        finally:
            loop.stop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_args: loop.add_callback(shutdown))
    logging.info("BF badminton API started on http://localhost:%s", settings.app_port)
    loop.start()


if __name__ == "__main__":
    main()
