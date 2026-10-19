# =============================================================================
# OA 管理系统 - 运行脚本（Windows PowerShell）
#
# 启动：后端（dev 用 runserver / prod 用 gunicorn）+ Celery Worker
# 用法（PowerShell）：
#   .\scripts\run.ps1                 # dev：runserver :8000 + celery
#   .\scripts\run.ps1 -Mode prod       # prod：gunicorn + celery
#   .\scripts\run.ps1 -Only backend    # 仅后端
#   .\scripts\run.ps1 -Only celery     # 仅 celery
#
# 停止：Ctrl+C
# =============================================================================
[CmdletBinding()]
param(
  [string]$Mode = "dev",
  [string]$Only = "",
  [string]$Port = "8000"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$BackendDir = (Resolve-Path (Join-Path $ScriptDir "..\backend")).Path
Push-Location $BackendDir

$venvPy = Join-Path $BackendDir ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) { Write-Error "未找到 .venv，请先运行 .\scripts\bootstrap_env.ps1"; exit 1 }

$settings = if ($Mode -eq "prod") { "config.settings.prod" } else { "config.settings.dev" }
$env:DJANGO_SETTINGS_MODULE = $settings
New-Item -ItemType Directory -Force -Path logs | Out-Null

$jobs = @()

if ($Only -ne "celery") {
  if ($Mode -eq "prod") {
    Write-Host "==> 启动 gunicorn (prod) on :$Port"
    $jobs += Start-Process -FilePath $venvPy -ArgumentList "manage.py","run_gunicorn","$Port" -NoNewWindow -PassThru
  } else {
    Write-Host "==> 启动 runserver (dev) on :$Port"
    $jobs += Start-Process -FilePath $venvPy -ArgumentList "manage.py","runserver","0.0.0.0:$Port" -NoNewWindow -PassThru
  }
}
if ($Only -ne "backend") {
  Write-Host "==> 启动 Celery worker"
  $celery = Join-Path $BackendDir ".venv\Scripts\celery.exe"
  $jobs += Start-Process -FilePath $celery -ArgumentList "-A","config","worker","-l","info" -NoNewWindow -PassThru -RedirectStandardOutput "logs/celery.log"
}

Write-Host "✅ 服务已启动（Ctrl+C 停止）。"
Write-Host "   API 前缀: http://127.0.0.1:$Port/api/v1/"
Write-Host "   Swagger:  http://127.0.0.1:$Port/api/docs/"
Write-Host "   ReDoc:    http://127.0.0.1:$Port/api/redoc/"
Write-Host "   Admin:    http://127.0.0.1:$Port/admin/"

try {
  # 等待用户中断
  while ($true) { Start-Sleep -Seconds 1 }
} finally {
  Write-Host "`n==> 正在停止服务 ..."
  foreach ($j in $jobs) { if (-not $j.HasExited) { Stop-Process -Id $j.Id -Force -ErrorAction SilentlyContinue } }
  Write-Host "==> 已停止。"
  Pop-Location
}
