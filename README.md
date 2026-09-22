# BF羽毛球馆管理平台部署说明

这份说明包含部署、启动和回归验证步骤。拿到仓库后，按下面流程准备 MySQL、Redis、后端和前端即可运行。

项目完善范围、分阶段验收标准和实施记录见 [项目完善计划](docs/项目完善计划.md)。

第二阶段的界面、导航、后台拆分与浏览器验证见 [设计与验收](docs/第二阶段设计与验收.md)。毕业演示可按 [独立演示环境](docs/演示环境.md) 创建新数据库，保留现有业务数据。

第三阶段的推荐、维护、核销、改期、经营统计和输入框修复见 [实施与验收](docs/第三阶段实施与验收.md)，业务术语见 [CONTEXT.md](CONTEXT.md)。

已有本地开发库的赛事、公告和球友圈内容，可使用 [内容填充与配图](docs/内容填充与配图.md) 中的预览/导入命令补充；与创建完整独立演示库的脚本分开使用。

预约回归检查（使用隔离样例，不写入 MySQL 或 Redis）：

```bash
cd backend
.venv/bin/python -B -m unittest discover -s tests -v
```

前端逻辑测试和生产构建：

```bash
cd frontend
npm test
npm run build
```

后端每 30 秒检查到期的待支付预约和已结束的预约；支付、查询等请求仍保留即时状态校验。使用率按当前启用场地、当前营业规则和预约时长计算，包含待支付占用，不代表实际到场率。

## 1. 环境要求

- Python 3.10+
- Node.js 18+ 和 npm
- MySQL 8.0+
- Redis 6.0+
- Git

建议先确认版本：

```bash
python3 --version
node --version
npm --version
mysql --version
redis-server --version
```

## 2. 获取代码

```bash
git clone <仓库地址> badminton_platform
cd badminton_platform
```

## 3. 配置后端环境变量

复制示例配置：

```bash
cp backend/.env.example backend/.env
```

按实际环境修改 `backend/.env`：

```dotenv
APP_ENV=dev
APP_PORT=8000
JWT_SECRET=请替换为足够长的随机字符串

MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=root
MYSQL_DATABASE=badminton_platform

REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_DB=0
```

生产环境必须修改 `JWT_SECRET`、数据库账号和数据库密码，不要使用示例值。

## 4. 初始化数据库

确认 MySQL 已启动后执行：

```bash
mysql -h127.0.0.1 -P3306 -uroot -p < sql/init.sql
```

`sql/init.sql` 会创建 `badminton_platform` 数据库、业务表、基础配置和初始管理员。

初始管理员：

```text
用户名：admin
密码：admin123
```

首次登录后请立即修改管理员密码。

如果是从旧版本数据库升级到当前版本，按顺序执行迁移脚本：

```bash
mysql -h127.0.0.1 -P3306 -uroot -p badminton_platform < scripts/upgrade_phase1_court_assets.sql
mysql -h127.0.0.1 -P3306 -uroot -p badminton_platform < scripts/upgrade_phase2_member_accounts.sql
mysql -h127.0.0.1 -P3306 -uroot -p badminton_platform < scripts/upgrade_phase3_notifications.sql
mysql -h127.0.0.1 -P3306 -uroot -p badminton_platform < scripts/upgrade_phase4_marketplace.sql
mysql -h127.0.0.1 -P3306 -uroot -p badminton_platform < scripts/upgrade_phase5_reservation_orders.sql
mysql -h127.0.0.1 -P3306 -uroot -p badminton_platform < scripts/upgrade_phase6_admin_refund_flow.sql
backend/.venv/bin/python scripts/migrate_booking_operations.py --database badminton_platform --apply
```

phase7 只新增维护、到场和改期历史表；可先省略 `--apply` 做只读预览，在停止业务写入的窗口升级并校验原数据合计。新库只需要执行 `sql/init.sql`。

## 5. 本地一键启动

启动前确认 MySQL 和 Redis 已经运行。

```bash
chmod +x start-dev.command stop-dev.command scripts/*.sh
./start-dev.command
```

启动成功后访问：

```text
前端：http://localhost:5188
后端：http://localhost:8000/api/health
```

停止服务：

```bash
./stop-dev.command
```

日志位置：

```text
logs/backend.log
logs/frontend.log
```

## 6. 手动启动后端

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py
```

后端默认监听：

```text
http://localhost:8000
```

健康检查：

```bash
curl http://localhost:8000/api/health
```

## 7. 手动启动前端

另开一个终端：

```bash
cd frontend
npm install
npm run dev
```

前端默认监听：

```text
http://localhost:5188
```

开发环境下 Vite 会把 `/api` 代理到 `http://localhost:8000`。

## 8. 生产部署参考

生产环境推荐方式：

1. MySQL 和 Redis 使用独立服务或服务器常驻进程。
2. 后端用 `backend/.venv/bin/python app.py` 运行，并由 systemd、Supervisor 或 pm2 管理进程。
3. 前端执行 `npm run build`，把 `frontend/dist` 交给 Nginx。
4. Nginx 负责静态文件和 `/api` 反向代理。

构建前端：

```bash
cd frontend
npm install
npm run build
```

后端生产启动示例：

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
APP_ENV=prod APP_PORT=8000 .venv/bin/python app.py
```

Nginx 示例：

```nginx
server {
    listen 80;
    server_name your-domain.com;

    root /path/to/badminton_platform/frontend/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

如果前端和后端不在同一个域名下，需要在前端构建时设置 API 地址，例如：

```bash
cd frontend
VITE_API_BASE_URL=https://api.example.com/api npm run build
```

## 9. 常见问题

### 后端启动后健康检查失败

检查：

```bash
tail -n 100 logs/backend.log
```

重点确认 MySQL、Redis 是否启动，`backend/.env` 中的账号密码和端口是否正确。

### 前端页面能打开但接口失败

开发环境检查 Vite 代理和后端端口：

```bash
curl http://localhost:8000/api/health
```

生产环境检查 Nginx `/api/` 反向代理配置。

### 数据库重复初始化

`sql/init.sql` 使用 `CREATE TABLE IF NOT EXISTS` 和幂等种子写法，重复执行不会清空业务数据。生产环境执行前仍建议先备份数据库。
