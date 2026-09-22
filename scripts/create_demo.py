#!/usr/bin/env python3
"""Create a fresh, isolated demonstration database; preview is the default.

Run with backend/.venv/bin/python scripts/create_demo.py --help.
Never overwrites an existing database or changes backend/.env.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import date, datetime, time, timedelta
import getpass
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def validate_database(name: str) -> str:
    if not re.fullmatch(r"badminton_demo_[a-z0-9_]{1,40}", name):
        raise ValueError("演示库名必须以 badminton_demo_ 开头，后缀只允许小写字母、数字和下划线。")
    return name


def build_dataset(today: date, now: datetime) -> dict[str, list[dict]]:
    tomorrow = today + timedelta(days=1)
    rows = []
    # Two upcoming bookings deliberately inserted in reverse chronological order.
    # Historic records also exceed a page to exercise summary and pagination.
    specs = [(tomorrow + timedelta(days=3), "confirmed", 1, 18),
             (tomorrow, "confirmed", 2, 18),
             (tomorrow, "pending", 3, 19)]
    specs += [(today - timedelta(days=n + 1), ["completed", "canceled", "expired"][n % 3], (n % 3) + 1, 17) for n in range(55)]
    for number, (day, status, court_id, hour) in enumerate(specs, 1):
        rows.append({"reservation_no": f"DEMO-R-{number:03}", "user_id": 2, "court_id": court_id,
                     "reserve_date": day, "start_time": f"{hour:02}:00", "end_time": f"{hour+1:02}:00",
                     "time_slot": f"{hour:02}:00-{hour+1:02}:00", "status": status,
                     "remark": "独立演示数据", "price_per_hour_cents": 12000, "duration_minutes": 60,
                     "original_amount_cents": 12000, "discount_amount_cents": 0,
                     "payable_amount_cents": 12000, "member_level_snapshot": "normal", "discount_rate": 100,
                     "points_awarded": 120 if status in ("completed", "confirmed") else 0,
                     "canceled_at": datetime.combine(day, time(12)) if status == "canceled" else None})
    return {
        "reservation": rows,
        "announcement": [
            {"title": "预约与入场须知", "content": "选好日期、场地与连续时段后，请及时完成余额支付。到场时可在我的预订中查看场次信息。", "status": 1, "created_by": 1},
            {"title": "会员服务说明", "content": "会员中心可以查看余额、有效期和消费明细。如需补充余额，请联系场馆工作人员。", "status": 1, "created_by": 1},
        ],
        "club_event": [{"title": title, "content": description, "location": "一号场",
                        "start_at": datetime.combine(today + timedelta(days=days), time(14)),
                        "end_at": datetime.combine(today + timedelta(days=days), time(16)),
                        "registration_deadline": datetime.combine(today + timedelta(days=days-1), time(22)),
                        "capacity": 16, "status": 1, "created_by": 1}
                       for title, description, days in [
                           ("周末双打交流", "两小时双打交流，欢迎不同水平的球友报名。请自备球拍并提前热身。", 3),
                           ("基础步法练习", "从启动到回位，一起练习基本步法。以轻量训练和交流为主。", 5)]],
        "community_post": [
            {"user_id": 2, "content": "今天练了反手高远球，发现放松握拍比一味发力更重要。下次准备多练几组步法。", "status": 1},
            {"user_id": 3, "content": "周末双打交流已报名，希望遇到节奏合拍的搭档！", "status": 1},
        ],
        "notification": [{"user_id": 2, "title": "欢迎来到 BF 羽毛球馆", "content": "先在场地预订中选好时间，再约上球友。这里是独立演示环境。", "category": "system", "created_by": 1}],
    }


async def insert(cursor, table: str, row: dict) -> int:
    columns = ', '.join(f'`{key}`' for key in row)
    await cursor.execute(f"INSERT INTO `{table}` ({columns}) VALUES ({', '.join(['%s'] * len(row))})", tuple(row.values()))
    return cursor.lastrowid


async def create_demo(database: str, password: str, today: date, now: datetime) -> dict:
    import aiomysql
    from dotenv import load_dotenv
    from config.settings import load_settings
    from utils.passwords import hash_password

    validate_database(database)
    if len(password) < 8:
        raise ValueError("请设置至少 8 位的演示账号密码。")
    load_dotenv(ROOT / 'backend/.env')
    settings = load_settings()
    if database == settings.mysql_database:
        raise ValueError("拒绝使用当前业务库。请使用新的独立库名。")
    connection = await aiomysql.connect(host=settings.mysql_host, port=settings.mysql_port,
        user=settings.mysql_user, password=settings.mysql_password, charset='utf8mb4', autocommit=True)
    dataset = build_dataset(today, now)
    try:
        async with connection.cursor() as cursor:
            await cursor.execute("SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME = %s", (database,))
            if await cursor.fetchone():
                raise ValueError("该库已存在，已停止且未修改任何数据。重新演示请换一个新的库名。")
            # No IF NOT EXISTS: a concurrent create must fail rather than reuse data.
            await cursor.execute(f"CREATE DATABASE `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci")
            await cursor.execute(f"USE `{database}`")
            text = (ROOT / 'sql/init.sql').read_text()
            schema = text[text.index('CREATE TABLE'):text.index('INSERT INTO config')]
            for statement in schema.split(';'):
                if statement.strip(): await cursor.execute(statement)
            # Reuse only non-account defaults; no default administrator is copied.
            for start, end in [('config', 'court'), ('court', 'user')]:
                await cursor.execute(text[text.index(f'INSERT INTO {start} ('):text.index(f'INSERT INTO {end} (')].strip().rstrip(';'))
            products = text[text.index('INSERT INTO shop_product ('):].strip().rstrip(';')
            await cursor.execute(products)
            await cursor.execute("CREATE TABLE demo_metadata (project VARCHAR(100), generated_at DATETIME)")
            await cursor.execute("INSERT INTO demo_metadata VALUES ('badminton_platform', %s)", (now,))
            await connection.begin()
            digest = hash_password(password)
            for username, nickname, role in [('demo_manager', '演示管理员', 'admin'), ('demo_player', '林间球友', 'user'), ('demo_partner', '周末搭档', 'user')]:
                uid = await insert(cursor, 'user', {'username': username, 'nickname': nickname, 'role': role, 'password_hash': digest, 'status': 1})
                await insert(cursor, 'member_account', {'user_id': uid, 'member_level': 'normal', 'balance_cents': 0, 'points': 0})
                await insert(cursor, 'member_account_transaction', {'user_id': uid, 'transaction_type': 'admin_adjust',
                    'balance_change_cents': 1000000, 'balance_before_cents': 0, 'balance_after_cents': 1000000,
                    'reason': '独立演示余额', 'operator_id': 1, 'operator_username': 'demo_manager'})
                await cursor.execute("UPDATE member_account SET balance_cents = 1000000 WHERE user_id = %s", (uid,))
            balance, points = 1000000, 0
            for row in dataset.pop('reservation'):
                rid = await insert(cursor, 'reservation', row)
                status = row['status']
                paid = status in ('confirmed', 'completed')
                reference = now if status in ('pending', 'confirmed') else datetime.combine(row['reserve_date'], time(12))
                await insert(cursor, 'reservation_order', {'order_no': row['reservation_no'].replace('-R-', '-O-'),
                    'reservation_id': rid, 'user_id': 2, 'status': 'paid' if paid else status,
                    'amount_cents': 12000, 'expires_at': reference + timedelta(minutes=15),
                    'paid_at': reference if paid else None, 'canceled_at': row['canceled_at']})
                if paid:
                    await insert(cursor, 'member_account_transaction', {'user_id': 2, 'reservation_id': rid,
                        'transaction_type': 'reservation_charge', 'balance_change_cents': -12000, 'points_change': 120,
                        'balance_before_cents': balance, 'balance_after_cents': balance-12000,
                        'points_before': points, 'points_after': points+120, 'reason': '独立演示预约支付'})
                    balance -= 12000
                    points += 120
            # Opening credit covers every seeded paid order; keep the ledger reconcilable.
            await cursor.execute("UPDATE member_account SET balance_cents = %s, points = %s WHERE user_id = 2", (balance, points))
            for table, rows in dataset.items():
                for row in rows: await insert(cursor, table, row)
            await cursor.execute("SELECT id FROM club_event ORDER BY id LIMIT 1")
            event_id = (await cursor.fetchone())[0]
            await insert(cursor, 'event_registration', {'event_id': event_id, 'user_id': 3, 'status': 'active'})
            await connection.commit()
    except Exception:
        await connection.rollback()
        raise
    finally:
        connection.close()
    return {'database': database, 'accounts': ['demo_manager', 'demo_player', 'demo_partner'],
            'reservation_count': 58, 'business_database_changed': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True, help='新的 badminton_demo_ 开头的数据库名')
    parser.add_argument('--date', type=date.fromisoformat, default=date.today(), help='演示基准日 YYYY-MM-DD，默认今天')
    parser.add_argument('--apply', action='store_true', help='实际创建新库；省略时只预览数据数量')
    args = parser.parse_args()
    try:
        validate_database(args.database)
        now = datetime.combine(args.date, datetime.now().time())
        if not args.apply:
            rows = build_dataset(args.date, now)
            print(json.dumps({'mode': 'preview', 'database': args.database, 'base_date': str(args.date),
                              'rows': {k: len(v) for k, v in rows.items()}, 'writes': 0}, ensure_ascii=False, indent=2))
            return
        password = os.environ.get('BF_DEMO_PASSWORD') or getpass.getpass('设置本次演示账号密码（不显示、不保存）：')
        print(json.dumps(asyncio.run(create_demo(args.database, password, args.date, now)), ensure_ascii=False, indent=2))
    except (ValueError, OSError) as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    main()
