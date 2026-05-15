from handlers.auth import LoginHandler, PasswordHandler, ProfileHandler, RegisterHandler
from handlers.health import HealthHandler


def build_routes() -> list[tuple[str, object]]:
    return [
        (r"/api/health", HealthHandler),
        (r"/api/admin/health", HealthHandler),
        (r"/api/auth/register", RegisterHandler),
        (r"/api/auth/login", LoginHandler),
        (r"/api/auth/profile", ProfileHandler),
        (r"/api/auth/password", PasswordHandler),
    ]
