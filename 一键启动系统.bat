@echo off
rem ===================================================================
rem  OA System - one click start  (just double click this file)
rem
rem  Starts MySQL + Redis + Django backend + Vite frontend + Celery,
rem  waits until the services are ready, then opens the browser.
rem
rem  Stop everything later with:  scripts\start_all.ps1 -Stop
rem ===================================================================
setlocal
set "PS1=%~dp0scripts\start_all.ps1"

if not exist "%PS1%" (
    echo [ERROR] Script not found: "%PS1%"
    echo.
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%" -WithCelery -Background -Open

if errorlevel 1 (
    echo.
    echo [ERROR] Startup failed. Please read the messages above.
    echo.
    pause
    exit /b 1
)

rem Give the user a moment to read the final summary before the window closes.
rem (ping is used instead of timeout: timeout fails when stdin is redirected)
ping -n 4 127.0.0.1 >nul
exit /b 0
