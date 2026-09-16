import asyncio
import getpass

from config.settings import load_settings
from repositories import database, user_repository
from utils.passwords import hash_password


async def create_admin() -> None:
    username = input("管理员用户名 [admin]: ").strip() or "admin"
    password = getpass.getpass("管理员密码: ")
    confirmation = getpass.getpass("再次输入密码: ")
    if len(password) < 6:
        raise SystemExit("密码长度不能少于6位")
    if password != confirmation:
        raise SystemExit("两次输入的密码不一致")

    settings = load_settings()
    password_hash = await asyncio.to_thread(hash_password, password)
    existing = await user_repository.get_user_by_username(settings, username)
    if existing is None:
        user_id = await user_repository.create_user(
            settings,
            username=username,
            password_hash=password_hash,
            nickname="系统管理员",
            contact="",
            role="admin",
        )
    else:
        user_id = existing["id"]
        await database.execute(
            settings,
            "UPDATE user SET password_hash = %s, role = 'admin', status = 1 WHERE id = %s",
            (password_hash, user_id),
        )

    await database.execute(
        settings,
        "INSERT IGNORE INTO member_account (user_id) VALUES (%s)",
        (user_id,),
    )
    await database.close_pool()
    print(f"管理员 {username} 已安全创建或更新。")


if __name__ == "__main__":
    asyncio.run(create_admin())
