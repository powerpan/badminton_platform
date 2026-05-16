# AGENTS.md

## Cursor Cloud specific instructions

### Architecture

This is a full-stack badminton court management platform with:
- **Backend**: Python 3.12 + Tornado 6.4 on port 8000 (`backend/app.py`)
- **Frontend**: Vue 3 + TypeScript + Vite + Element Plus on port 5188 (`frontend/`)
- **Database**: MySQL 8.0 (`badminton_platform` database, root/root)
- **Cache**: Redis on default port 6379

### Starting services

Before running the application, MySQL and Redis must be started:

```bash
sudo service mysql start
sudo chmod 755 /var/run/mysqld/   # required for non-root MySQL client access
sudo service redis-server start
```

Start backend:
```bash
cd /workspace/backend && .venv/bin/python app.py
```

Start frontend dev server:
```bash
cd /workspace/frontend && npm run dev
```

### Key gotchas

- **MySQL socket permissions**: After starting MySQL, you must run `sudo chmod 755 /var/run/mysqld/` to allow non-root users (including the Python backend) to connect via the Unix socket.
- **Captcha on login**: The login endpoint requires a captcha. Get one from `GET /api/auth/captcha`, read the code from Redis (`redis-cli GET auth:captcha:<captcha_id>`), then pass `captcha_id` and `captcha_code` in the login request body.
- **Default admin**: username `admin`, password `admin123456`. After first login the API sets `must_change_password: true` but does not enforce it for API calls.
- **No ESLint configured**: The type-check command is `vue-tsc --noEmit` (also runs during `npm run build`).
- **Backend .env**: Copy `.env.example` to `.env` in the backend directory if it doesn't exist. Default credentials use `root/root` for MySQL.
- **Health check**: `curl http://localhost:8000/api/health` verifies API, MySQL, and Redis connectivity in one call.
- **DB initialization**: `mysql -uroot -proot < sql/init.sql` creates the database and seeds default data. It is idempotent (uses `ON DUPLICATE KEY UPDATE`).

### Testing

- **Backend**: No automated test suite yet. Use the health check and API calls for verification.
- **Frontend type check**: `cd frontend && npx vue-tsc --noEmit`
- **Frontend build**: `cd frontend && npm run build`
