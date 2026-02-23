@echo off
setlocal EnableDelayedExpansion

cd /d %~dp0
chcp 65001 >nul
set PYTHONUTF8=1

echo ========================================================
echo       JupyterHub Training Platform - One Click Start
echo ========================================================
echo.

REM Check Docker availability
docker info >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not running or not installed. Start Docker Desktop first.
    pause
    exit /b 1
)

echo [Precheck] Validating required ports...
set "REQUIRED_PORTS=8080 8001 8002 8003 3001 9090"
set "PORT_CONFLICT=0"
set "CURRENT_PROJECT="
for /f "delims=" %%P in ('docker compose ps --format "{{.Project}}" 2^>nul') do (
    if not defined CURRENT_PROJECT set "CURRENT_PROJECT=%%P"
)
if defined CURRENT_PROJECT (
    echo [Precheck] Current compose project: !CURRENT_PROJECT!
)

for %%P in (%REQUIRED_PORTS%) do (
    set "PORT_IN_USE=0"
    set "OWN_STACK_USES_PORT=0"
    for /f "tokens=1,* delims= " %%A in ('docker ps --format "{{.Names}} {{.Ports}}" ^| findstr /C:":%%P->"') do (
        set "CONTAINER_NAME=%%A"
        set "IS_OWN_STACK=0"

        if defined CURRENT_PROJECT (
            echo !CONTAINER_NAME! | findstr /B /I /C:"!CURRENT_PROJECT!-" >nul
            if not errorlevel 1 set "IS_OWN_STACK=1"
        )

        if "!IS_OWN_STACK!"=="1" (
            set "OWN_STACK_USES_PORT=1"
        )

        if "!IS_OWN_STACK!"=="0" (
            if "!PORT_IN_USE!"=="0" (
                echo [ERROR] Port %%P is already in use by running container^(s^):
            )
            echo         %%A %%B
            set "PORT_IN_USE=1"
            set "PORT_CONFLICT=1"
        )
    )

    if "!PORT_IN_USE!"=="0" if "!OWN_STACK_USES_PORT!"=="0" (
        powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort %%P -State Listen -ErrorAction SilentlyContinue) { exit 1 } else { exit 0 }" >nul 2>&1
        if errorlevel 1 (
            echo [ERROR] Port %%P is already in use by another process.
            set "PORT_CONFLICT=1"
        )
    )
)

if "!PORT_CONFLICT!"=="1" (
    echo.
    echo [TIP] Stop conflicting services, then rerun start.bat.
    echo [TIP] Inspect running containers:
    echo       docker ps --format "table {{.Names}}	{{.Ports}}"
    echo [TIP] Stop this project's current stack:
    echo       docker compose down
    pause
    exit /b 1
)

echo [1/4] Build Docker images...
set "USE_NO_BUILD=0"
docker compose build
if errorlevel 1 (
    echo [WARN] Build failed. Falling back to start with --no-build.
    set "USE_NO_BUILD=1"
)

echo.
echo [2/4] Start services...
if "%USE_NO_BUILD%"=="1" (
    docker compose up -d --no-build
) else (
    docker compose up -d
)
if errorlevel 1 (
    echo [ERROR] Service startup failed.
    if "%USE_NO_BUILD%"=="1" (
        echo [TIP] --no-build was used. Make sure required images already exist locally.
    )
    pause
    exit /b 1
)

echo.
echo [3/4] Wait for services to initialize (~30s)...
timeout /t 30 /nobreak >nul

echo.
echo [4/4] Initialize database and seed data...
docker compose exec -T experiment-manager python init_db.py
if errorlevel 1 (
    echo [WARN] init_db.py failed. You can run it manually after startup.
)

echo.
echo ========================================================
echo                    Deployment Complete
echo ========================================================
echo.
echo Access URLs:
echo.
echo   - Unified Entry: http://localhost:8080
echo   - Experiment Manager API: http://localhost:8001/docs
echo   - AI Assistant API: http://localhost:8002/docs
echo   - Grafana: http://localhost:3001  (admin/admin)
echo.
echo Press any key to close...
pause >nul
