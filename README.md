# BF羽毛球馆管理平台

本项目是基于 Tornado 的 BF 羽毛球馆管理平台，采用前后端分离架构：

- 前端：Vue3、Vue Router、Pinia、Axios、Element Plus、Vite
- 后端：Python Tornado
- 数据库：MySQL
- 缓存：Redis
- 认证：JWT

当前阶段已完成开发框架骨架、用户认证闭环、会员账户闭环、场地预约闭环、站内通知、公告详情、帮助中心、后台基础管理、统计分析、操作日志、预约状态自动处理、验证码、找回密码、基础安全增强和 Element Plus 前端重构。普通用户可以查看场地、选择时间段、创建预约、查看和取消自己的预约、查看通知和公告详情；管理员可以管理用户、会员账户、场地、预约、公告、全员通知、预约规则配置、运营统计和操作日志。

## 当前实现状态

已完成：

- Tornado 后端基础应用、路由和统一 JSON 响应。
- MySQL 连接池和用户数据访问封装。
- Redis / MySQL / API 健康检查。
- 用户注册、登录、验证码、JWT 鉴权、个人资料、修改密码、找回密码。
- 会员账户查询，包含等级、有效期、余额、积分、固定折扣和当前实际折扣。
- 场地列表、按规则生成时间段、时间段状态查询。
- 场地资产和价格已接入数据库，支持场地图片、标签、容纳人数和每小时价格展示。
- 预约创建、Redis 临时锁、MySQL 时间重叠冲突校验。
- 预约写入使用 MySQL 短事务再次锁定用户、会员账户、场地和有效预约记录，降低高并发下的重复预约风险。
- 预约创建时写入价格、时长、会员等级、折扣、积分和金额快照，历史预约不受后续场地改价或会员等级变化影响。
- 预约成功扣减会员余额并发放积分；用户或管理员取消预约会退回余额并扣回本次积分。
- 我的预约列表和未开始预约取消。
- 管理员用户新增、启用/禁用、角色修改。
- 管理员会员账户调整，支持等级、有效期、余额增减、积分增减和调整原因。
- 管理员场地新增、编辑、启停。
- 管理员预约列表、详情和取消。
- 管理员公告发布、编辑、隐藏。
- 站内通知列表、未读数、单条已读和全部已读。
- 预约成功、取消预约、会员账户调整和公告发布会自动生成站内通知。
- 管理员支持向全部启用账号群发站内通知。
- 公告中心和公告详情页已接入前端路由。
- 帮助中心已提供预约、取消、会员和场地使用规则说明。
- 管理员规则配置查询和更新。
- 后台统计接口和统计视图：预约总量、今日预约、活跃用户、场地使用率、热门时间段、用户活跃度。
- 管理员关键操作日志写入和日志查询。
- 预约状态自动处理：已结束的 `confirmed` 预约自动转为 `completed`。
- Refresh token、退出登录、登录失败锁定和默认管理员改密提醒。
- 密码重置会清理对应用户的 refresh token，降低旧登录态继续使用的风险。
- 后台用户、场地、预约、公告、日志分页与筛选。
- 禁用用户、停用场地前会检查未来有效预约，存在预约时拒绝操作。
- 用户取消预约、管理员取消预约、禁用用户、停用场地、重置密码、修改角色、会员调整、隐藏公告和保存规则等敏感操作已加入二次确认。
- 后台会员调整、场地编辑、公告编辑和规则配置编辑已改为弹窗表单，避免旧数据回填到顶部新增表单。
- 预约冲突、空状态和加载状态的前端提示优化。
- Vue3 前端骨架、Axios 请求封装、Pinia 登录态保存。
- `/login`、`/register`、`/forgot-password`、`/profile`、`/courts`、`/reservations`、`/notifications`、`/announcements`、`/announcements/:id`、`/help`、`/admin` 页面。
- 路由守卫：未登录跳转登录页，普通用户不能访问管理后台。
- 初始化 SQL：核心表、默认配置、测试场地、默认管理员账号。

待开发：

- 后端自动化接口测试。
- Docker 部署和生产环境配置。

## 目录结构

```text
badminton_platform/
  backend/        Tornado 后端
  frontend/       Vue3 前端
  sql/            数据库初始化脚本
  docs/           软件工程文档
  scripts/        启动和数据库升级脚本
```

本地开发也可以直接使用根目录的一键脚本：

```text
cd /Users/ericpan/game_project/badminton_platform
./start-dev.command
./stop-dev.command
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
- 会员账户表
- 会员账户流水表
- 场地表
- 预约表
- 公告表
- 站内通知表
- 系统配置表
- 操作日志表
- 默认系统配置和测试场地
- 默认管理员账号：`admin / admin123456`

默认账号仅用于本地开发和演示，正式部署前应修改密码和 `JWT_SECRET`。

已有本地库升级到当前版本时，按顺序执行：

```text
mysql -uroot -p badminton_platform < /Users/ericpan/game_project/badminton_platform/scripts/upgrade_phase1_court_assets.sql
mysql -uroot -p badminton_platform < /Users/ericpan/game_project/badminton_platform/scripts/upgrade_phase2_member_accounts.sql
mysql -uroot -p badminton_platform < /Users/ericpan/game_project/badminton_platform/scripts/upgrade_phase3_notifications.sql
```

升级脚本会为场地补充价格、图片、标签、容纳人数，为历史预约补齐费用快照字段，并创建会员账户、会员流水和预约会员快照字段。两个升级脚本均按字段存在性判断，可重复执行。

## 认证接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/auth/register` | 注册普通用户 |
| POST | `/api/auth/login` | 登录并返回 JWT |
| GET | `/api/auth/captcha` | 获取图形验证码 |
| POST | `/api/auth/refresh` | 使用 refresh token 刷新登录态 |
| POST | `/api/auth/logout` | 退出登录并删除 refresh token |
| POST | `/api/auth/password-reset/request` | 校验用户名、联系方式和验证码，申请重置密码 |
| POST | `/api/auth/password-reset/confirm` | 使用重置凭证提交新密码 |
| GET | `/api/auth/profile` | 获取当前用户信息 |
| PUT | `/api/auth/profile` | 修改昵称和联系方式 |
| PUT | `/api/auth/password` | 修改密码 |

## 业务接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/announcements` | 查询显示中的公告 |
| GET | `/api/announcements/{id}` | 查询公告详情 |
| GET | `/api/notifications` | 查询我的站内通知 |
| GET | `/api/notifications/unread-count` | 查询未读通知数量 |
| PUT | `/api/notifications/{id}/read` | 标记单条通知已读 |
| PUT | `/api/notifications/read-all` | 标记全部通知已读 |
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
| PUT | `/api/admin/users/{id}/member` | 调整会员账户 |
| PUT | `/api/admin/users/{id}/password` | 管理员重置用户密码 |
| GET/POST | `/api/admin/courts` | 场地列表和新增场地 |
| PUT | `/api/admin/courts/{id}` | 编辑场地 |
| PUT | `/api/admin/courts/{id}/status` | 启用或停用场地 |
| GET | `/api/admin/reservations` | 查询全部预约 |
| GET | `/api/admin/reservations/{id}` | 查询预约详情 |
| PUT | `/api/admin/reservations/{id}/cancel` | 管理员取消预约 |
| GET/POST | `/api/admin/announcements` | 公告列表和发布公告 |
| PUT | `/api/admin/announcements/{id}` | 编辑公告 |
| PUT | `/api/admin/announcements/{id}/status` | 显示或隐藏公告 |
| POST | `/api/admin/notifications/broadcast` | 向全部启用账号群发站内通知 |
| GET | `/api/admin/configs` | 查询规则配置 |
| PUT | `/api/admin/configs/{config_key}` | 更新规则配置 |
| GET | `/api/admin/statistics/overview` | 查询后台统计总览 |
| GET | `/api/admin/statistics/courts` | 查询场地使用率统计 |
| GET | `/api/admin/statistics/time-slots` | 查询热门时间段统计 |
| GET | `/api/admin/statistics/users` | 查询用户活跃度统计 |
| GET | `/api/admin/logs` | 查询管理员操作日志 |

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

下一阶段建议优先推“活动赛事、球友圈和商城入口”：

1. 活动赛事先支持活动列表、详情和报名。
2. 球友圈先支持简单动态列表和文本发布。
3. 商城先支持商品展示和购买说明，不接入真实库存和支付。
4. 管理端补齐活动和商品的基础维护能力。
5. 同步更新数据库设计、接口设计和当前实现状态文档。

当前第三阶段已完成站内通知、公告详情和帮助中心。下一阶段可以继续把侧栏中仍禁用的活动赛事、球友圈和商城入口逐步变成可访问页面。
