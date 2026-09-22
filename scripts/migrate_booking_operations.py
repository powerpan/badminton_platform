#!/usr/bin/env python3
"""Apply the additive phase 7 schema to an explicitly named existing database."""
import argparse
import asyncio
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))


async def migrate(database, apply=False):
    import aiomysql
    from dotenv import load_dotenv
    from config.settings import load_settings
    if not re.fullmatch(r'[a-zA-Z0-9_]{1,64}', database):
        raise ValueError('数据库名称不合法')
    load_dotenv(ROOT / 'backend/.env')
    settings = load_settings()
    connection = await aiomysql.connect(host=settings.mysql_host, port=settings.mysql_port,
        user=settings.mysql_user, password=settings.mysql_password, db=database, autocommit=True)
    try:
        async with connection.cursor() as cursor:
            await cursor.execute('SELECT COUNT(*), COALESCE(SUM(payable_amount_cents),0) FROM reservation')
            reservations = await cursor.fetchone()
            await cursor.execute('SELECT COUNT(*), COALESCE(SUM(balance_cents),0), COALESCE(SUM(points),0) FROM member_account')
            accounts = await cursor.fetchone()
            if apply:
                script = (ROOT / 'scripts/upgrade_phase7_booking_operations.sql').read_text()
                for sql in script.split(';'):
                    if sql.strip(): await cursor.execute(sql)
                await cursor.execute('SELECT COUNT(*), COALESCE(SUM(payable_amount_cents),0) FROM reservation')
                assert reservations == await cursor.fetchone(), '预约数据校验不一致'
                await cursor.execute('SELECT COUNT(*), COALESCE(SUM(balance_cents),0), COALESCE(SUM(points),0) FROM member_account')
                assert accounts == await cursor.fetchone(), '会员数据校验不一致'
            return {'database': database, 'mode': 'apply' if apply else 'preview',
                    'tables': ['court_block','reservation_attendance','reservation_change'],
                    'existing_data_unchanged': True if apply else None}
    finally:
        connection.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    print(json.dumps(asyncio.run(migrate(args.database, args.apply)), ensure_ascii=False))
