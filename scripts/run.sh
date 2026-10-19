#!/usr/bin/env bash
# =============================================================================
# OA 管理系统 - 运行脚本（Linux / macOS）
#
# 启动：后端（dev 用 runserver / prod 用 gunicorn）+ Celery Worker
# 用法：
#   ./scripts/run.sh            # dev：runserver 0.0.0.0:8000 + celery
#   ./scripts/run.sh prod       # prod：gunicorn + celery
#   ./scripts/run.sh backend    # 仅后端
#   ./scripts/run.sh celery     # 仅 celery
#
# 停止：Ctrl+C（会同时结束后端与 celery 子进程）
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/../backend" && pwd)"
MODE="${1:-dev}"
PORT="${PORT:-8000}"

cd "$BACKEND_DIR"
source .venv/bin/activate

mkdir -p logs
PIDS=()

cleanup() {
  echo ""
  echo "==> 正在停止服务 ..."
  for pid in "${PIDS[@]:-}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
  echo "==> 已停止。"
}
trap cleanup EXIT INT TERM

start_backend() {
  if [ "$MODE" = "prod" ]; then
    echo "==> 启动 gunicorn (prod) on :$PORT"
    DJANGO_SETTINGS_MODULE=config.settings.prod gunicorn config.wsgi:application \
      --bind "0.0.0.0:$PORT" --workers 4 --timeout 120 \
      --access-logfile logs/gunicorn_access.log --error-logfile logs/gunicorn_error.log &
  else
    echo "==> 启动 runserver (dev) on :$PORT"
    DJANGO_SETTINGS_MODULE=config.settings.dev python manage.py runserver "0.0.0.0:$PORT" &
  fi
  PIDS+=($!)
}

start_celery() {
  echo "==> 启动 Celery worker"
  DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.dev}" \
    celery -A config worker -l info --concurrency 2 \
    >> logs/celery.log 2>&1 &
  PIDS+=($!)
}

case "$MODE" in
  backend) start_backend ;;
  celery)  start_celery ;;
  dev|prod)
    if [ "$MODE" = "prod" ]; then export DJANGO_SETTINGS_MODULE=config.settings.prod; fi
    start_backend
    start_celery
    ;;
  *) echo "未知模式: $MODE (支持 dev|prod|backend|celery)"; exit 1 ;;
esac

echo "✅ 服务已启动（Ctrl+C 停止）。"
echo "   API 前缀:   http://127.0.0.1:$PORT/api/v1/"
echo "   Swagger:    http://127.0.0.1:$PORT/api/docs/"
echo "   ReDoc:      http://127.0.0.1:$PORT/api/redoc/"
echo "   Admin:      http://127.0.0.1:$PORT/admin/"

# 前台挂起，等待任意子进程退出
wait
