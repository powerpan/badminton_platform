# BF羽毛球馆管理平台

本项目是基于 Tornado 的 BF 羽毛球馆管理平台，采用前后端分离架构：

- 前端：Vue3、Vue Router、Pinia、Axios、Vite
- 后端：Python Tornado
- 数据库：MySQL
- 缓存：Redis
- 认证：JWT

当前阶段已完成开发框架骨架和用户认证闭环，包含后端健康检查、数据库初始化 SQL、JWT 登录认证、前端登录注册页面、个人中心、路由守卫和管理员权限拦截。

## 当前实现状态

已完成：

- Tornado 后端基础应用、路由和统一 JSON 响应。
- MySQL 连接池和用户数据访问封装。
- Redis / MySQL / API 健康检查。
- 用户注册、登录、JWT 鉴权、个人资料、修改密码。
- Vue3 前端骨架、Axios 请求封装、Pinia 登录态保存。
- `/login`、`/register`、`/profile`、`/courts`、`/reservations`、`/admin` 基础页面。
- 路由守卫：未登录跳转登录页，普通用户不能访问管理后台。
- 初始化 SQL：核心表、默认配置、测试场地、默认管理员账号。

待开发：

- 场地列表接口和页面数据接入。
- 场地时间段状态查询。
- 预约创建、Redis 锁和 MySQL 冲突校验。
- 我的预约、取消预约。
- 管理员用户、场地、预约和公告管理。
- 统计分析、规则配置和操作日志页面。

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

管理员健康检查需要登录后携带管理员 token：

```text
GET /api/admin/health
Authorization: Bearer <admin-token>
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

默认账号仅用于本地开发和演示，正式部署前应修改密码和 `JWT_SECRET`。

## 认证接口

当前已实现的认证接口：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/auth/register` | 注册普通用户 |
| POST | `/api/auth/login` | 登录并返回 JWT |
| GET | `/api/auth/profile` | 获取当前用户信息 |
| PUT | `/api/auth/profile` | 修改昵称和联系方式 |
| PUT | `/api/auth/password` | 修改密码 |

统一响应格式：

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

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

下一阶段建议优先推“场地与预约基础闭环”：

1. 后端场地列表接口：`GET /api/courts`。
2. 后端时间段状态接口：`GET /api/courts/{court_id}/slots?date=YYYY-MM-DD`。
3. 前端场地预约页接入真实数据。
4. 后端预约创建接口：`POST /api/reservations`。
5. Redis 预约锁：同一场地、同一日期、同一时间段只允许一个请求成功。
6. MySQL 最终冲突校验：防止 Redis key 丢失后产生重复预约。
7. 我的预约接口和页面：`GET /api/reservations/my`。
8. 取消预约接口：`PUT /api/reservations/{id}/cancel`。

完成这一阶段后，普通用户就能从登录到预约、查看、取消形成完整业务闭环。
