# BF羽毛球馆管理平台

本项目是基于 Tornado 的 BF 羽毛球馆管理平台，采用前后端分离架构：

- 前端：Vue3、Vue Router、Pinia、Axios、Vite
- 后端：Python Tornado
- 数据库：MySQL
- 缓存：Redis
- 认证：JWT

当前阶段已完成开发框架骨架，包含后端健康检查、数据库初始化 SQL、前端基础页面和路由。

## 目录结构

```text
badminton_platform/
  backend/        Tornado 后端
  frontend/       Vue3 前端
  sql/            数据库初始化脚本
  docs/           软件工程文档
  scripts/        后续启动和维护脚本
```

## 后端启动

推荐直接使用脚本：

```text
cd /Users/ericpan/game_project/badminton_platform
./scripts/start_backend.sh
```

也可以手动启动：

```text
cd /Users/ericpan/game_project/badminton_platform/backend
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py
```

后端默认地址：

```text
http://localhost:8000
```

健康检查：

```text
curl http://localhost:8000/api/health
```

## 数据库初始化

先确认 MySQL 已启动，然后执行：

```text
mysql -uroot -p < /Users/ericpan/game_project/badminton_platform/sql/init.sql
```

初始化脚本会创建：

- `badminton_platform` 数据库
- 用户表
- 场地表
- 预约表
- 公告表
- 系统配置表
- 操作日志表
- 默认系统配置和测试场地
- 默认管理员账号：`admin / admin123456`

## Redis

后端健康检查会连接默认 Redis：

```text
127.0.0.1:6379
```

可以用下面命令确认 Redis 是否可用：

```text
redis-cli ping
```

预期返回：

```text
PONG
```

## 前端启动

推荐直接使用脚本：

```text
cd /Users/ericpan/game_project/badminton_platform
./scripts/start_frontend.sh
```

也可以手动启动：

```text
cd /Users/ericpan/game_project/badminton_platform/frontend
npm install
npm run dev
```

前端默认地址：

```text
http://localhost:5188
```

Vite 已配置 `/api` 代理到：

```text
http://localhost:8000
```

## 下一步开发顺序

1. 实现场地列表和场地时间段查询。
2. 实现预约创建、Redis 加锁和 MySQL 冲突校验。
3. 实现我的预约和取消预约。
4. 实现管理员用户、场地、预约和公告管理。
5. 实现统计分析、系统配置和操作日志。
