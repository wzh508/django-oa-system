# =============================================================================
# OA 管理系统 - 一键启动全部服务（Windows PowerShell）
#
# 覆盖「从零跑通」所需的四条命脉：
#   0) MySQL   Windows 服务 MySQL80，:3306
#   1) Redis   便携版，:6379        —— 缓存 + Celery Broker
#   2) 后端    Django runserver，:8000
#   3) 前端    Vite dev server，:5173
#   4) Celery  worker（可选，加 -WithCelery）
#
# 幂等：已监听该端口的服务会跳过，不会重复起。
#
# 用法（在 PowerShell 中，项目根目录下）：
#   .\scripts\start_all.ps1                       # 起 MySQL + Redis + 后端 + 前端
#   .\scripts\start_all.ps1 -WithCelery            # 再加 Celery worker
#   .\scripts\start_all.ps1 -Background            # 后端改为新窗口后台跑，本窗口不阻塞
#   .\scripts\start_all.ps1 -Open                  # 全部就绪后自动打开浏览器（隐含 -Background）
#   .\scripts\start_all.ps1 -Stop                  # 关闭后端 / 前端 / Redis
# =============================================================================
[CmdletBinding()]
param(
  [switch]$WithCelery,
  [switch]$Stop,
  [switch]$Background,          # 后端改为新窗口后台运行，本窗口不阻塞
  [switch]$Open,                # 全部就绪后自动打开浏览器进入系统（隐含 -Background）
  [int]$ReadyTimeoutSec = 120   # -Open 时等待服务就绪的最长秒数
)

if ($Open) { $Background = $true }

$ErrorActionPreference = "Stop"

$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ProjectRoot = (Resolve-Path (Join-Path $ScriptDir "..")).Path
$BackendDir  = Join-Path $ProjectRoot "backend"
$FrontendDir = Join-Path $ProjectRoot "frontend"
$RedisDir    = Join-Path $ProjectRoot ".runtime\redis"

$RedisExe  = Join-Path $RedisDir "redis-server.exe"
$RedisConf = Join-Path $RedisDir "redis.windows.conf"
$VenvPy    = Join-Path $BackendDir ".venv\Scripts\python.exe"
$CeleryExe = Join-Path $BackendDir ".venv\Scripts\celery.exe"

$FrontendUrl = "http://127.0.0.1:5173/"


function Test-Port {
  param([int]$Port)
  $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
  return [bool]$conn
}

function Get-PortPid {
  param([int]$Port)
  $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
  if ($conn) { return ($conn | Select-Object -First 1).OwningProcess }
  return $null
}

function Wait-Port {
  param([int]$Port, [int]$TimeoutSec = 60)
  $deadline = (Get-Date).AddSeconds($TimeoutSec)
  while ((Get-Date) -lt $deadline) {
    if (Test-Port -Port $Port) { return $true }
    Start-Sleep -Milliseconds 700
  }
  return (Test-Port -Port $Port)
}

function Test-CeleryRunning {
  # celery.exe 与 python -m celery 两种起法都要认出来
  $procs = Get-CimInstance Win32_Process -Filter "Name='celery.exe' OR Name='python.exe'" -ErrorAction SilentlyContinue
  return [bool]($procs | Where-Object { $_.CommandLine -match 'celery' -and $_.CommandLine -match 'worker' })
}

function Show-Urls {
  Write-Host ""
  Write-Host "────────────────────────────────────────────────"
  Write-Host "  前端入口:   $FrontendUrl"
  Write-Host "  API 前缀:   http://127.0.0.1:8000/api/v1/"
  Write-Host "  Swagger:    http://127.0.0.1:8000/api/docs/"
  Write-Host "  ReDoc:      http://127.0.0.1:8000/api/redoc/"
  Write-Host "  Admin:      http://127.0.0.1:8000/admin/"
  Write-Host "  演示账号:   admin / Oa@123456"
  Write-Host "────────────────────────────────────────────────"
}

# ---------------------------------------------------------------- 停止模式
if ($Stop) {
  Write-Host "==> 正在停止 8000 / 5173 / 6379 ..."
  foreach ($p in @(8000, 5173, 6379)) {
    $procId = Get-PortPid -Port $p
    if ($procId) {
      try {
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        Write-Host "    已停止端口 $p (PID $procId)"
      } catch {
        Write-Host "    端口 $p 停止失败：$($_.Exception.Message)"
      }
    } else {
      Write-Host "    端口 $p 本来就没在跑"
    }
  }
  Write-Host "==> 完成。（Celery 若单独开过窗口，请手动关闭）"
  exit 0
}

# ---------------------------------------------------------------- 前置检查
if (-not (Test-Path $VenvPy)) {
  Write-Error "未找到 $VenvPy`n请先运行：.\scripts\bootstrap_env.ps1"
  exit 1
}
if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
  Write-Error "前端依赖未安装，请先执行：cd frontend; npm install"
  exit 1
}

Write-Host "════════════════════════════════════════════════"
Write-Host " OA 系统启动中    项目根目录: $ProjectRoot"
Write-Host "════════════════════════════════════════════════"

# ---------------------------------------------------------------- 0) MySQL
if (Test-Port -Port 3306) {
  Write-Host "==> [0/4] MySQL      :3306  已在运行，跳过"
} else {
  $svc = Get-Service -Name "MySQL80" -ErrorAction SilentlyContinue
  if ($svc) {
    Write-Host "==> [0/4] MySQL      :3306  正在启动 Windows 服务 MySQL80 ..."
    try {
      Start-Service -Name "MySQL80" -ErrorAction Stop
      if (Wait-Port -Port 3306 -TimeoutSec 30) { Write-Host "        启动成功" }
      else { Write-Host "        警告：3306 仍未监听，请检查 MySQL80 服务" }
    } catch {
      Write-Host "        启动失败（可能需要管理员权限）：$($_.Exception.Message)"
    }
  } else {
    Write-Host "==> [0/4] MySQL      未找到 MySQL80 服务，请手动确认数据库可用"
  }
}

# ---------------------------------------------------------------- 1) Redis
if (Test-Port -Port 6379) {
  Write-Host "==> [1/4] Redis      :6379  已在运行，跳过"
} elseif (Test-Path $RedisExe) {
  Write-Host "==> [1/4] Redis      :6379  正在启动（便携版）..."
  Start-Process -FilePath $RedisExe -ArgumentList "`"$RedisConf`"" `
    -WorkingDirectory $RedisDir -WindowStyle Minimized
  if (Wait-Port -Port 6379 -TimeoutSec 15) { Write-Host "        启动成功" }
  else { Write-Host "        警告：6379 未监听，缓存/Celery 会回退或报错" }
} else {
  Write-Host "==> [1/4] Redis      未找到便携版 $RedisExe"
  Write-Host "        可把 .env 的 CACHE_BACKEND 改为 locmem、CELERY_BROKER_BACKEND 改为 filesystem"
}

# ---------------------------------------------------------------- 2) 前端（先起，因为它后台跑）
if (Test-Port -Port 5173) {
  Write-Host "==> [2/4] 前端 Vite   :5173  已在运行，跳过"
} else {
  Write-Host "==> [2/4] 前端 Vite   :5173  正在启动 ..."
  Start-Process -FilePath "npm.cmd" -ArgumentList "run","dev" `
    -WorkingDirectory $FrontendDir -WindowStyle Normal
  if (Wait-Port -Port 5173 -TimeoutSec 60) { Write-Host "        启动成功" }
  else { Write-Host "        警告：5173 未监听，请看新开的窗口里的报错" }
}

# ---------------------------------------------------------------- 3) Celery（可选）
if ($WithCelery) {
  if (Test-CeleryRunning) {
    Write-Host "==> [3/4] Celery worker 已在运行，跳过"
  } elseif (Test-Path $CeleryExe) {
    Write-Host "==> [3/4] Celery worker 正在启动 ..."
    Start-Process -FilePath $CeleryExe `
      -ArgumentList "-A","config","worker","-l","info","-P","solo" `
      -WorkingDirectory $BackendDir -WindowStyle Normal
  } else {
    Write-Host "==> [3/4] 未找到 celery.exe，跳过"
  }
} else {
  Write-Host "==> [3/4] Celery 未启动（加 -WithCelery 可启用定时任务/催办）"
}

# ---------------------------------------------------------------- 4) 后端
New-Item -ItemType Directory -Force -Path (Join-Path $BackendDir "logs") | Out-Null
$env:DJANGO_SETTINGS_MODULE = "config.settings.dev"

if (Test-Port -Port 8000) {
  Write-Host "==> [4/4] 后端       :8000  已在运行，跳过"
} elseif ($Background) {
  Write-Host "==> [4/4] 后端       :8000  正在后台启动（新窗口）..."
  Start-Process -FilePath $VenvPy `
    -ArgumentList "manage.py","runserver","0.0.0.0:8000" `
    -WorkingDirectory $BackendDir -WindowStyle Normal
  if (Wait-Port -Port 8000 -TimeoutSec 60) { Write-Host "        启动成功" }
  else { Write-Host "        警告：8000 未监听，请看新开的窗口里的报错" }
} else {
  Show-Urls
  Write-Host ""
  Write-Host "==> [4/4] 即将在前台启动后端，Ctrl+C 即停止后端。"
  Write-Host ""
  Push-Location $BackendDir
  try {
    & $VenvPy manage.py runserver 0.0.0.0:8000
  } finally {
    Pop-Location
  }
  exit 0
}

Show-Urls

# ---------------------------------------------------------------- 就绪等待 + 自动开浏览器
if ($Open) {
  Write-Host ""
  Write-Host "==> 等待服务就绪（最多 $ReadyTimeoutSec 秒）..."
  $deadline = (Get-Date).AddSeconds($ReadyTimeoutSec)
  while ((Get-Date) -lt $deadline) {
    if ((Test-Port -Port 5173) -and (Test-Port -Port 8000)) { break }
    Start-Sleep -Milliseconds 800
  }
  if ((Test-Port -Port 5173) -and (Test-Port -Port 8000)) {
    Write-Host "==> 全部服务已就绪，正在打开浏览器进入系统 ..."
    try {
      Start-Process $FrontendUrl
    } catch {
      Write-Host "        自动打开浏览器失败，请手动访问 $FrontendUrl"
    }
  } else {
    Write-Host "==> 警告：等待超时，服务未全部就绪，请查看各服务窗口日志。"
  }
}

Write-Host ""
Write-Host "==> 启动流程结束。停止服务：.\scripts\start_all.ps1 -Stop"
