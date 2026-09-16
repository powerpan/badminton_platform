import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


def _int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value == "":
        return default
    return int(raw_value)


@dataclass(frozen=True)
class Settings:
    app_env: str
    app_port: int
    jwt_secret: str
    jwt_expire_seconds: int
    jwt_refresh_expire_seconds: int
    login_fail_max: int
    login_fail_window_seconds: int
    login_lock_seconds: int
    captcha_expire_seconds: int
    mysql_host: str
    mysql_port: int
    mysql_user: str
    mysql_password: str
    mysql_database: str
    redis_host: str
    redis_port: int
    redis_db: int


def load_settings() -> Settings:
    return Settings(
        app_env=os.getenv("APP_ENV", "dev"),
        app_port=_int_env("APP_PORT", 8000),
        jwt_secret=os.getenv("JWT_SECRET", "change-me"),
        jwt_expire_seconds=_int_env("JWT_EXPIRE_SECONDS", 86400),
        jwt_refresh_expire_seconds=_int_env("JWT_REFRESH_EXPIRE_SECONDS", 604800),
        login_fail_max=_int_env("LOGIN_FAIL_MAX", 5),
        login_fail_window_seconds=_int_env("LOGIN_FAIL_WINDOW_SECONDS", 600),
        login_lock_seconds=_int_env("LOGIN_LOCK_SECONDS", 600),
        captcha_expire_seconds=_int_env("CAPTCHA_EXPIRE_SECONDS", 300),
        mysql_host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        mysql_port=_int_env("MYSQL_PORT", 3306),
        mysql_user=os.getenv("MYSQL_USER", "root"),
        mysql_password=os.getenv("MYSQL_PASSWORD", "root"),
        mysql_database=os.getenv("MYSQL_DATABASE", "badminton_platform"),
        redis_host=os.getenv("REDIS_HOST", "127.0.0.1"),
        redis_port=_int_env("REDIS_PORT", 6379),
        redis_db=_int_env("REDIS_DB", 0),
    )
