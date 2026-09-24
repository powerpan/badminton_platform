#!/usr/bin/env python3
"""Phase 8 schema migration; preview by default, on an explicitly named database.

Source of truth: sql/init.sql. Only additive definitions and the two documented
nullable customer columns are allowed. Does not seed users or fabricate payments.
"""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
NEW_TABLES = {'payment_order', 'payment_command', 'payment_refund', 'recharge_order', 'shop_pickup', 'shop_stock_hold'}
NULLABLE_CUSTOMERS = {'reservation', 'reservation_order'}


def validate_database(name):
    if not re.fullmatch(r'[A-Za-z0-9_]{1,64}', name) or name.lower() in {'mysql', 'sys', 'information_schema', 'performance_schema'}:
        raise ValueError('必须指定合法业务库名，不能操作系统库')
    return name


def target_tables():
    sql = (ROOT / 'sql/init.sql').read_text()
    return {m[1]: m[0] for m in re.finditer(
        r'CREATE TABLE IF NOT EXISTS (\w+) \(.*?\) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;', sql, re.S)}


def definitions(sql):
    # Split at top-level commas only (DECIMAL, indexes and CHECKs contain commas).
    body = sql[sql.index('(') + 1:sql.rindex(') ENGINE')]
    parts, depth, quote, start = [], 0, None, 0
    for i, char in enumerate(body):
        if quote:
            if char == quote: quote = None
        elif char in "'\"`": quote = char
        elif char == '(': depth += 1
        elif char == ')': depth -= 1
        elif char == ',' and depth == 0:
            parts.append(body[start:i].strip()); start = i + 1
    parts.append(body[start:].strip())
    return parts


async def schema(cursor, database):
    await cursor.execute('''SELECT TABLE_NAME,COLUMN_NAME,COLUMN_TYPE,IS_NULLABLE,COLUMN_DEFAULT,EXTRA,
        CHARACTER_SET_NAME,COLLATION_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=%s''', (database,))
    columns = {}
    for row in await cursor.fetchall(): columns.setdefault(row['TABLE_NAME'], {})[row['COLUMN_NAME']] = row
    await cursor.execute('''SELECT TABLE_NAME,INDEX_NAME,NON_UNIQUE,SEQ_IN_INDEX,COLUMN_NAME
        FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=%s ORDER BY TABLE_NAME,INDEX_NAME,SEQ_IN_INDEX''', (database,))
    indexes = {}
    for row in await cursor.fetchall(): indexes.setdefault(row['TABLE_NAME'], {}).setdefault(row['INDEX_NAME'], []).append(row)
    await cursor.execute('''SELECT TABLE_NAME,CONSTRAINT_NAME,CONSTRAINT_TYPE
        FROM information_schema.TABLE_CONSTRAINTS WHERE TABLE_SCHEMA=%s''', (database,))
    constraints = {}
    for row in await cursor.fetchall(): constraints.setdefault(row['TABLE_NAME'], {})[row['CONSTRAINT_NAME']] = row
    return columns, indexes, constraints


async def plan(cursor, database):
    columns, indexes, constraints = await schema(cursor, database)
    targets = target_tables()
    missing_legacy = set(targets) - NEW_TABLES - set(columns)
    if missing_legacy:
        raise ValueError('请先完成原有阶段升级；缺表：' + ', '.join(sorted(missing_legacy)))
    actions = []
    for table, sql in targets.items():
        if table not in columns:
            actions.append(sql)
            continue
        for definition in definitions(sql):
            words = definition.split()
            if words[0] in {'PRIMARY', 'UNIQUE', 'KEY', 'CONSTRAINT'}:
                if words[0] == 'PRIMARY': name = 'PRIMARY'
                elif words[0] == 'UNIQUE': name = words[2]
                else: name = words[1]
                present = constraints.get(table, {}) if words[0] == 'CONSTRAINT' else indexes.get(table, {})
                if name not in present:
                    actions.append(f'ALTER TABLE `{table}` ADD {definition}')
            else:
                name = words[0]
                if name not in columns[table]:
                    actions.append(f'ALTER TABLE `{table}` ADD COLUMN {definition}')
                elif name == 'user_id' and table in NULLABLE_CUSTOMERS and columns[table][name]['IS_NULLABLE'] == 'NO':
                    # MySQL permits relaxing nullability without dropping the FK.
                    actions.append(f'ALTER TABLE `{table}` MODIFY COLUMN {definition}')
    # Create the independent new tables before adding FKs from existing tables.
    return [a for a in actions if a.startswith('CREATE')] + [a for a in actions if not a.startswith('CREATE')]


async def fingerprints(cursor, columns):
    """Hash every pre-existing column and row, without printing personal data."""
    result = {}
    for table, fields in sorted(columns.items()):
        if 'id' not in fields and 'user_id' not in fields and 'reservation_id' not in fields:
            raise ValueError(f'未知表 {table}，请人工确认迁移范围')
        order = next(key for key in ('id', 'user_id', 'reservation_id') if key in fields)
        field_sql = ','.join(f'`{name}`' for name in sorted(fields))
        await cursor.execute(f'SELECT {field_sql} FROM `{table}` ORDER BY `{order}`')
        digest, count = hashlib.sha256(), 0
        while True:
            rows = await cursor.fetchmany(500)
            if not rows: break
            for row in rows:
                digest.update(json.dumps(row, sort_keys=True, default=str, ensure_ascii=False).encode())
                digest.update(b'\n'); count += 1
        result[table] = {'rows': count, 'sha256': digest.hexdigest()}
    return result


async def migrate(database, apply=False):
    import aiomysql
    from dotenv import load_dotenv
    from config.settings import load_settings
    validate_database(database)
    load_dotenv(ROOT / 'backend/.env')
    settings = load_settings()
    connection = await aiomysql.connect(host=settings.mysql_host, port=settings.mysql_port,
        user=settings.mysql_user, password=settings.mysql_password, db=database, autocommit=True)
    try:
        async with connection.cursor(aiomysql.DictCursor) as cursor:
            # Prevent two copies of this tool from racing on DDL; does not stop business writes.
            await cursor.execute('SELECT GET_LOCK(%s, 0) AS acquired', ('bf_phase8_' + database[:50],))
            if (await cursor.fetchone())['acquired'] != 1:
                raise RuntimeError('同库迁移正在运行，本次退出')
            before_columns, _, _ = await schema(cursor, database)
            before_columns = {t: c for t, c in before_columns.items() if t in target_tables()}
            actions = await plan(cursor, database)
            before = await fingerprints(cursor, before_columns)
            applied = []
            if apply:
                for sql in actions:
                    await cursor.execute(sql)
                    applied.append(sql)
                if before != await fingerprints(cursor, before_columns):
                    raise RuntimeError('原有记录发生变化，停止升级并检查备份及并发写入；不要直接回滚 DDL')
                if await plan(cursor, database):
                    raise RuntimeError('结构尚未完全升级，请保存现场检查')
            return {'database': database, 'mode': 'apply' if apply else 'preview',
                'planned_statements': actions, 'applied_count': len(applied),
                'existing_data_unchanged': True if apply else None, 'before': before}
    finally:
        connection.close()  # Also releases the session advisory lock.


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--writes-stopped', action='store_true', help='Confirm writes stopped and restorable backup available (or disposable test DB)')
    args = parser.parse_args()
    if args.apply and not args.writes_stopped:
        parser.error('--apply 必须同时提供 --writes-stopped；实际库须先停写并验证备份')
    print(json.dumps(asyncio.run(migrate(args.database, args.apply)), ensure_ascii=False, indent=2))
