# BF羽毛球馆管理平台

本项目是基于 Tornado 的 BF 羽毛球馆管理平台，采用前后端分离架构：

- 前端：Vue3、Vue Router、Pinia、Axios、Vite
- 后端：Python Tornado
- 数据库：MySQL
- 缓存：Redis
- 认证：JWT

当前阶段已完成开发框架骨架、用户认证闭环、场地预约闭环和后台基础管理。普通用户可以查看场地、选择时间段、创建预约、查看和取消自己的预约；管理员可以管理用户、场地、预约、公告和预约规则配置。

## 当前实现状态

已完成：

- Tornado 后端基础应用、路由和统一 JSON 响应。
- MySQL 连接池和用户数据访问封装。
- Redis / MySQL / API 健康检查。
- 用户注册、登录、JWT 鉴权、个人资料、修改密码。
- 场地列表、按规则生成时间段、时间段状态查询。
- 预约创建、Redis 临时锁、MySQL 时间重叠冲突校验。
- 我的预约列表和未开始预约取消。
- 管理员用户新增、启用/禁用、角色修改。
- 管理员场地新增、编辑、启停。
- 管理员预约列表、详情和取消。
- 管理员公告发布、编辑、隐藏。
- 管理员规则配置查询和更新。
- Vue3 前端骨架、Axios 请求封装、Pinia 登录态保存。
- `/login`、`/register`、`/profile`、`/courts`、`/reservations`、`/admin` 页面。
- 路由守卫：未登录跳转登录页，普通用户不能访问管理后台。
- 初始化 SQL：核心表、默认配置、测试场地、默认管理员账号。

待开发：

- 统计分析图表。
- 操作日志查询页面。
- 预约状态自动完成、过期处理。
- 找回密码、刷新 token、验证码等安全增强。
- Docker 部署和生产环境配置。

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

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/auth/register` | 注册普通用户 |
| POST | `/api/auth/login` | 登录并返回 JWT |
| GET | `/api/auth/profile` | 获取当前用户信息 |
| PUT | `/api/auth/profile` | 修改昵称和联系方式 |
| PUT | `/api/auth/password` | 修改密码 |

## 业务接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/announcements` | 查询显示中的公告 |
| GET | `/api/courts` | 查询启用场地列表 |
| GET | `/api/courts/{court_id}/slots?date=YYYY-MM-DD` | 查询场地时间段状态 |
| POST | `/api/reservations` | 创建预约 |
| GET | `/api/reservations/my` | 查询我的预约 |
| PUT | `/api/reservations/{id}/cancel` | 取消我的预约 |

## 管理员接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET/POST | `/api/admin/users` | 用户列表和新增用户 |
| PUT | `/api/admin/users/{id}/status` | 启用或禁用用户 |
| PUT | `/api/admin/users/{id}/role` | 修改用户角色 |
| GET/POST | `/api/admin/courts` | 场地列表和新增场地 |
| PUT | `/api/admin/courts/{id}` | 编辑场地 |
| PUT | `/api/admin/courts/{id}/status` | 启用或停用场地 |
| GET | `/api/admin/reservations` | 查询全部预约 |
| GET | `/api/admin/reservations/{id}` | 查询预约详情 |
| PUT | `/api/admin/reservations/{id}/cancel` | 管理员取消预约 |
| GET/POST | `/api/admin/announcements` | 公告列表和发布公告 |
| PUT | `/api/admin/announcements/{id}` | 编辑公告 |
| PUT | `/api/admin/announcements/{id}/status` | 显示或隐藏公告 |
| GET | `/api/admin/configs` | 查询规则配置 |
| PUT | `/api/admin/configs/{config_key}` | 更新规则配置 |

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

下一阶段建议优先推“统计分析与运维增强”：

1. 增加后台统计接口：预约总量、今日预约、活跃用户、场地使用率。
2. 增加统计图表页面：按场地、日期、时间段展示预约分布。
3. 增加操作日志写入和查询页面，记录管理员关键操作。
4. 增加预约自动过期和自动完成处理。
5. 补一批后端自动化接口测试，覆盖当前核心业务。
6. 准备 Docker Compose 或一键启动脚本，降低演示部署成本。

当前已完成场地与预约基础闭环、后台管理与规则配置。下一阶段应优先提升可展示性、可追踪性和验收稳定性。
