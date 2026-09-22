#!/usr/bin/env python3
"""Add labeled demonstration content to the existing LOCAL development database.

Preview by default; --apply inserts missing rows in one transaction. Existing
content is never overwritten. No accounts, registrations, notifications, money,
reservations or court blocks are created. Dates are relative to --date/today.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import date, datetime, time, timedelta
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))


def dataset(today: date) -> dict[str, list[dict]]:
    saturday = today + timedelta(days=(5 - today.weekday()) % 7 or 7)
    event_specs = [
        ('新手上场 · 基础步法与高远球', saturday, 9, 11, 12,
         '适合刚开始打球、希望建立基本动作的球友。先做动态热身，再分组练习握拍、启动回位和高远球，最后进行半场对打。',
         '自备球拍、室内运动鞋和饮用水；提前 15 分钟集合。按个人报名，不要求有搭档。'),
        ('周末双打积分交流赛', saturday, 14, 17, 16,
         '16 人双打交流，现场配对后分组循环。示例赛制为每局 21 分、一局定胜负，20 平后先领先 2 分获胜，29 平后先到 30 分获胜。分组结束后安排交叉交流。',
         '按个人报名，集合后配对；提前 20 分钟签到。此处为活动信息和报名演示，不提供自动编排对阵或积分排名。'),
        ('周日混双搭档交流', saturday + timedelta(days=1), 14, 16, 16,
         '以双打站位、前后场轮转和搭档沟通为主题。先做发接发配合练习，再轮换搭档进行短局交流，适合已有基本击球能力的球友。',
         '可与搭档分别报名，也可个人参加现场配对；提前 15 分钟集合，自备球拍。'),
        ('下班后 · 轻松双打夜', saturday + timedelta(days=4), 19, 21, 12,
         '两小时轻松交流，按到场人数轮转上场。每轮短局结束后换组，兼顾不同水平球友的上场时间，以练习配合和认识搭档为主。',
         '按个人报名；下班后时间可能变化，请在活动开始前及时取消无法参加的报名，方便其他球友加入。'),
        ('单打循环挑战赛', saturday + timedelta(days=7), 14, 17, 12,
         '面向能够完成全场移动的球友。现场抽签分组，采用 15 分短局循环，先到 15 分者获胜；每轮之间安排休息，以实战检验落点与回位。',
         '提前 20 分钟签到；自备球拍、饮水和替换衣物。本文赛制仅用于毕业项目活动内容演示。'),
        ('发接发专项 · 网前控制练习', saturday + timedelta(days=8), 10, 12, 12,
         '围绕双打前三拍安排练习：短发球落点、接发推扑选择、网前放网与挑球。两人一组轮换，最后通过限定前三拍的小对抗复习。',
         '欢迎有基础的球友参加，按个人报名；提前 15 分钟集合，练习中相互观察并交流动作感受。'),
    ]
    events = []
    for title, day, start, end, capacity, intro, notes in event_specs:
        events.append({
            'title': f'【演示】{title}',
            'content': f'{intro}\n\n参与说明\n{notes}\n\n演示说明\n本活动为毕业项目示例，可体验报名和取消流程，不代表球馆实际举办安排；报名不扣余额，也不自动占用预约场地。',
            'location': 'BF 羽毛球馆（演示地点，具体场地以现场安排为准）',
            'start_at': datetime.combine(day, time(start)),
            'end_at': datetime.combine(day, time(end)),
            'registration_deadline': datetime.combine(day - timedelta(days=1), time(22)),
            'capacity': capacity, 'status': 1,
        })
    notices = [
        ('第一次来打球：预约与入场指南',
         '在“场地预订”选择日期、场地和连续时段，核对金额后提交，再完成会员余额支付。待支付订单到期会释放占用。到场前可在“我的预订”查看时间和场地编号；建议提前热身，自备球拍、室内运动鞋和饮水。'),
        ('活动报名与取消说明',
         '进入“活动赛事”查看活动详情、开始时间、截止时间和剩余名额。登录后可以报名，也可以在详情页取消报名；名额以实际报名记录为准。当前标有“演示”的活动用于毕业项目操作展示，不收取费用，不构成真实活动通知。'),
        ('会员余额、优惠与消费明细',
         '会员中心展示余额、会员有效期和消费明细。待支付预约会占用部分可用余额；费用确认时会重新核对价格与会员权益。需要补充余额时请联系管理员，取消符合条件的已支付预约后，退款退回会员余额。'),
        ('球友圈交流与场地礼仪',
         '欢迎分享训练心得、搭档配合和器材使用经验。发帖时请避免公开手机号、证件或其他个人资料。打球前充分热身，轮换上场时主动沟通；离场前带走水瓶与废弃物，遇到场地问题可向工作人员反映。'),
    ]
    posts = [
        '新手交流｜第一次到馆打球，可以先准备球拍、室内运动鞋和水。大家觉得入门时最值得优先练的是高远球，还是回位步法？欢迎分享自己的练习顺序。',
        '双打话题｜搭档之间提前说清楚“我来”“你来”，往往比临时抢同一个球更有帮助。你们习惯怎样约定中路球和前后场轮转？',
        '练习打卡｜给下一次训练定一个小目标：先练 10 分钟短发球，再练两组启动回位，最后对打时观察自己的落点。欢迎在这里分享你的训练安排。',
        '器材交流｜手胶打滑时，握拍往往会不自觉变紧。球友们通常按什么标准更换手胶：使用次数、吸汗表现，还是表面磨损？',
        '活动讨论｜活动页已经准备了新手训练、双打交流和单打挑战等演示场次。想先体验哪一种？可以进入详情查看时间与名额，试一试报名流程。',
        '场边小提醒｜热身时先给肩、腕、踝一点准备时间；轮换休息时补水，离场前一起检查有没有遗落球拍和水杯。也欢迎补充你常用的出门装备清单。',
    ]
    return {
        'club_event': events,
        'announcement': [{'title': f'【演示】{title}', 'content': f'{body}\n\n本条为毕业项目服务内容示例。', 'status': 1} for title, body in notices],
        'community_post': [{'content': f'【演示话题】{body}', 'status': 1} for body in posts],
    }


async def seed(today: date, apply: bool) -> dict:
    import aiomysql
    from dotenv import load_dotenv
    load_dotenv(ROOT / 'backend/.env')
    from config.settings import load_settings
    from services.event_service import _event_payload
    from services.announcement_service import _validate_content
    settings = load_settings()
    if settings.mysql_host not in {'localhost', '127.0.0.1', '::1'} or settings.app_env.lower() not in {'dev', 'development', 'local', 'test'}:
        raise ValueError('此脚本仅允许本机开发环境，拒绝向远程或生产环境写入演示内容。')
    content = dataset(today)
    for row in content['club_event']:
        _event_payload(row)
    for row in content['announcement']:
        _validate_content(row['title'], row['content'])
    assert all(len(row['content']) <= 1000 for row in content['community_post'])
    connection = await aiomysql.connect(host=settings.mysql_host, port=settings.mysql_port,
        user=settings.mysql_user, password=settings.mysql_password, db=settings.mysql_database,
        charset='utf8mb4', autocommit=False, connect_timeout=5)
    report = {'mode': 'apply' if apply else 'preview', 'database': settings.mysql_database,
              'base_date': str(today), 'items': {}, 'inserted': 0, 'skipped': 0}
    locked = False
    try:
        async with connection.cursor(aiomysql.DictCursor) as cursor:
            if apply:
                await cursor.execute("SELECT GET_LOCK(%s, 5) AS acquired", (f'bf_content:{settings.mysql_database}'[:64],))
                locked = (await cursor.fetchone())['acquired'] == 1
                if not locked:
                    raise ValueError('另一个内容导入正在运行，请稍后重试。')
            await connection.begin()
            await cursor.execute("SELECT id, username FROM user WHERE role='admin' AND status=1 ORDER BY id LIMIT 1")
            actor = await cursor.fetchone()
            if not actor:
                raise ValueError('当前库缺少启用的管理员，已停止。')
            for table, rows in content.items():
                report['items'][table] = []
                key = 'content' if table == 'community_post' else 'title'
                for original in rows:
                    row = {**original, 'user_id' if table == 'community_post' else 'created_by': actor['id']}
                    await cursor.execute(f'SELECT id FROM `{table}` WHERE `{key}`=%s LIMIT 1', (row[key],))
                    existing = await cursor.fetchone()
                    item = {'title': row.get('title', row['content'].split('｜')[0]), 'action': 'skip' if existing else 'insert'}
                    if table == 'club_event':
                        item.update(start_at=str(row['start_at']), registration_deadline=str(row['registration_deadline']))
                    if existing:
                        item['id'] = existing['id']
                        report['skipped'] += 1
                    elif apply:
                        columns = ','.join(f'`{column}`' for column in row)
                        await cursor.execute(f'INSERT INTO `{table}` ({columns}) VALUES ({",".join(["%s"] * len(row))})', tuple(row.values()))
                        item['id'] = cursor.lastrowid
                        report['inserted'] += 1
                    report['items'][table].append(item)
            if apply and report['inserted']:
                await cursor.execute('''INSERT INTO operation_log (user_id,username,role,module,action,target_type,detail,ip)
                    VALUES (%s,%s,'admin','content','seed_demo_content','content_batch',%s,'127.0.0.1')''',
                    (actor['id'], actor['username'], json.dumps(report, ensure_ascii=False)))
            if apply:
                await connection.commit()
            else:
                await connection.rollback()
    except Exception:
        await connection.rollback()
        raise
    finally:
        if locked:
            async with connection.cursor() as cursor:
                await cursor.execute('SELECT RELEASE_LOCK(%s)', (f'bf_content:{settings.mysql_database}'[:64],))
        connection.close()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--date', type=date.fromisoformat, default=date.today())
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    try:
        print(json.dumps(asyncio.run(seed(args.date, args.apply)), ensure_ascii=False, indent=2))
    except Exception as error:
        parser.exit(1, f'内容导入失败，未提交本次事务：{error}\n')


if __name__ == '__main__':
    main()
