from typing import Any

from config.settings import Settings
from repositories.database import execute, fetch_all, fetch_one


async def list_configs(settings: Settings) -> list[dict[str, Any]]:
    return await fetch_all(
        settings,
        """
        SELECT id, config_key, config_value, description, updated_by, created_at, updated_at
        FROM config
        ORDER BY config_key ASC
        """,
    )


async def get_config(settings: Settings, config_key: str) -> dict[str, Any] | None:
    return await fetch_one(
        settings,
        """
        SELECT id, config_key, config_value, description, updated_by, created_at, updated_at
        FROM config
        WHERE config_key = %s
        """,
        (config_key,),
    )


async def update_config(
    settings: Settings,
    *,
    config_key: str,
    config_value: str,
    updated_by: int | None,
) -> None:
    await execute(
        settings,
        """
        UPDATE config
        SET config_value = %s, updated_by = %s
        WHERE config_key = %s
        """,
        (config_value, updated_by, config_key),
    )
