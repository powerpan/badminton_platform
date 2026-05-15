import logging

import tornado.ioloop
import tornado.web

from config.settings import load_settings
from routes import build_routes


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
    app.listen(settings.app_port)
    logging.info("BF badminton API started on http://localhost:%s", settings.app_port)
    tornado.ioloop.IOLoop.current().start()


if __name__ == "__main__":
    main()
