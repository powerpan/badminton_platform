#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$ROOT_DIR/logs"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5188}"
BACKEND_HEALTH_URL="http://localhost:${BACKEND_PORT}/api/health"
FRONTEND_URL="http://localhost:${FRONTEND_PORT}"

mkdir -p "$LOG_DIR"

echo "Stopping old development services first..."
bash "$ROOT_DIR/stop-dev.command"

echo "Starting backend on port $BACKEND_PORT..."
: > "$LOG_DIR/backend.log"
nohup bash -c 'cd "$1" && APP_PORT="$2" bash "$1/scripts/start_backend.sh"' bash "$ROOT_DIR" "$BACKEND_PORT" >> "$LOG_DIR/backend.log" 2>&1 &
BACKEND_PID=$!
echo "$BACKEND_PID" > "$LOG_DIR/backend.pid"

echo "Waiting for backend health check..."
backend_ready=0
for _ in $(seq 1 60); do
  if curl -fsS "$BACKEND_HEALTH_URL" >/dev/null 2>&1; then
    backend_ready=1
    break
  fi
  if ! kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if [ "$backend_ready" != "1" ]; then
  echo "Backend failed to start. Recent backend log:"
  tail -n 80 "$LOG_DIR/backend.log" || true
  exit 1
fi

echo "Backend is ready: $BACKEND_HEALTH_URL"
echo "Starting frontend on port $FRONTEND_PORT..."
: > "$LOG_DIR/frontend.log"
nohup bash -c 'cd "$1" && bash "$1/scripts/start_frontend.sh"' bash "$ROOT_DIR" >> "$LOG_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!
echo "$FRONTEND_PID" > "$LOG_DIR/frontend.pid"

echo "Waiting for frontend..."
frontend_ready=0
for _ in $(seq 1 60); do
  if curl -fsS "$FRONTEND_URL" >/dev/null 2>&1; then
    frontend_ready=1
    break
  fi
  if ! kill -0 "$FRONTEND_PID" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if [ "$frontend_ready" != "1" ]; then
  echo "Frontend failed to start. Recent frontend log:"
  tail -n 80 "$LOG_DIR/frontend.log" || true
  bash "$ROOT_DIR/stop-dev.command"
  exit 1
fi

echo "Development services started."
echo "Backend:  $BACKEND_HEALTH_URL"
echo "Frontend: $FRONTEND_URL"
echo "Logs:"
echo "  $LOG_DIR/backend.log"
echo "  $LOG_DIR/frontend.log"
