# =============================================================================
# OA 管理系统 - 环境初始化脚本（Windows PowerShell）
#
# 功能：与 bootstrap_env.sh 一致（建 venv / 装依赖 / 迁移 / collectstatic /
#       初始化基础数据 / 可选种子业务数据）。
#
# 用法（在 PowerShell 中）：
#   .\scripts\bootstrap_env.ps1                 # 默认 dev
#   .\scripts\bootstrap_env.ps1 -Env prod        # 生产环境
#   .\scripts\bootstrap_env.ps1 -Seed            # 额外写入演示业务数据
#
# 前置依赖：Python 3.11+，MySQL（或把 .env 的 DB_ENGINE 改为 sqlite），
#          Redis（或把 .env 的 CACHE_BACKEND / CELERY_BROKER_BACKEND 改为 locmem/filesystem）
# =============================================================================
[CmdletBinding()]
param(
  [string]$Env = "dev",
  [switch]$Seed
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ProjectRoot = (Resolve-Path (Join-Path $ScriptDir "..")).Path
$BackendDir = Join-Path $ProjectRoot "backend"

switch ($Env) {
  "dev"  { $DJANGO_SETTINGS_MODULE = "config.settings.dev" }
  "prod" { $DJANGO_SETTINGS_MODULE = "config.settings.prod" }
  default { Write-Error "未知环境: $Env (支持 dev|prod)"; exit 1 }
}

Write-Host "==> 项目根目录: $ProjectRoot"
Write-Host "==> 后端目录:   $BackendDir"
Write-Host "==> Django 环境: $DJANGO_SETTINGS_MODULE"

Push-Location $BackendDir

# 1. 虚拟环境
if (-not (Test-Path ".venv")) {
  Write-Host "==> 创建虚拟环境 .venv ..."
  python -m venv .venv
}
$venvPy = Join-Path $BackendDir ".venv\Scripts\python.exe"
$venvPip = Join-Path $BackendDir ".venv\Scripts\pip.exe"

# 2. 安装依赖
Write-Host "==> 安装后端依赖 ..."
& $venvPy -m pip install --upgrade pip
& $venvPip install -r requirements.txt

# 3. 迁移
Write-Host "==> 执行数据库迁移 ..."
& $venvPy manage.py migrate --noinput

# 4. 静态资源
Write-Host "==> 采集静态资源 ..."
& $venvPy manage.py collectstatic --noinput

# 5. 基础数据
Write-Host "==> 初始化基础数据（权限/角色/菜单/演示账号）..."
& $venvPy manage.py init_base --force-perms

# 6. 种子业务数据（可选）
if ($Seed) {
  Write-Host "==> 写入演示业务数据 ..."
  & $venvPy manage.py init_expense 2>$null
  & $venvPy manage.py init_lowcode 2>$null
}

Pop-Location
Write-Host ""
Write-Host "✅ 环境初始化完成。"
Write-Host "   启动后端:  $DJANGO_SETTINGS_MODULE ./scripts/run.ps1"
Write-Host "   API 文档:  http://127.0.0.1:8000/api/docs/"
