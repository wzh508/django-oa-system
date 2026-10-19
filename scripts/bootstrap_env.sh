#!/usr/bin/env bash
# =============================================================================
# OA 管理系统 - 环境初始化脚本（Linux / macOS）
#
# 功能：
#   1. 创建 Python 虚拟环境（backend/.venv）
#   2. 安装后端依赖（requirements.txt）
#   3. 执行数据库迁移
#   4. 采集静态资源（collectstatic）
#   5. 初始化基础数据（权限点 / 角色 / 菜单 / 部门 / 演示账号）
#   6. 可选：写入种子业务数据（报销 / 低代码表单）
#
# 用法：
#   ./scripts/bootstrap_env.sh            # 默认 dev 环境
#   ./scripts/bootstrap_env.sh prod       # 生产环境（DJANGO_SETTINGS_MODULE=config.settings.prod）
#   ./scripts/bootstrap_env.sh --seed     # 额外写入演示业务数据
#
# 前置依赖：Python 3.11+，MySQL（或把 .env 的 DB_ENGINE 改为 sqlite），
#          Redis（或把 .env 的 CACHE_BACKEND / CELERY_BROKER_BACKEND 改为 locmem/filesystem）
# =============================================================================
set -euo pipefail

# ---- 路径自定位 ----
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
ENV_NAME="${1:-dev}"
SEED=0
for a in "$@"; do [ "$a" = "--seed" ] && SEED=1; done

case "$ENV_NAME" in
  dev)  DJANGO_SETTINGS_MODULE=config.settings.dev ;;
  prod) DJANGO_SETTINGS_MODULE=config.settings.prod ;;
  *) echo "未知环境: $ENV_NAME (支持 dev|prod)"; exit 1 ;;
esac

echo "==> 项目根目录: $PROJECT_ROOT"
echo "==> 后端目录:   $BACKEND_DIR"
echo "==> Django 环境: $DJANGO_SETTINGS_MODULE"

cd "$BACKEND_DIR"

# ---- 1. 虚拟环境 ----
if [ ! -d ".venv" ]; then
  echo "==> 创建虚拟环境 .venv ..."
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

# ---- 2. 安装依赖 ----
echo "==> 安装后端依赖 ..."
python -m pip install --upgrade pip
pip install -r requirements.txt

# ---- 3. 迁移 ----
echo "==> 执行数据库迁移 ..."
python manage.py migrate --noinput

# ---- 4. 静态资源 ----
echo "==> 采集静态资源 ..."
python manage.py collectstatic --noinput || true

# ---- 5. 基础数据 ----
echo "==> 初始化基础数据（权限/角色/菜单/演示账号）..."
python manage.py init_base --force-perms

# ---- 6. 种子业务数据（可选）----
if [ "$SEED" = "1" ]; then
  echo "==> 写入演示业务数据 ..."
  python manage.py init_expense 2>/dev/null || true
  python manage.py init_lowcode  2>/dev/null || true
fi

echo ""
echo "✅ 环境初始化完成。"
echo "   启动后端:  DJANGO_SETTINGS_MODULE=$DJANGO_SETTINGS_MODULE ./scripts/run.sh"
echo "   API 文档:  http://127.0.0.1:8000/api/docs/"
