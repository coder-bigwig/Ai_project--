@echo off
setlocal

cd /d %~dp0

echo [dev] Starting backend containers...
docker start training-postgres training-redis training-experiment-manager training-ai-assistant >nul 2>&1
if %errorlevel% neq 0 (
  echo [dev] Existing backend containers not found. Falling back to docker compose.
  docker compose up -d postgres redis experiment-manager ai-assistant
  if %errorlevel% neq 0 (
    echo [dev] Failed to start backend services.
    echo [dev] If this is first run, make sure Docker can pull base images, then run start.bat once.
    exit /b 1
  )
)

echo [dev] Stopping production frontend/nginx containers to avoid stale page on :8080 ...
docker stop training-frontend training-nginx >nul 2>&1

echo [dev] Installing frontend dependencies if needed...
if not exist frontend\node_modules\react-scripts (
  cd frontend
  call npm install
  if %errorlevel% neq 0 (
    echo [dev] npm install failed.
    exit /b 1
  )
  cd ..
)

if /I "%SKIP_FRONTEND: =%"=="1" (
  echo [dev] SKIP_FRONTEND=1, skip starting React dev server.
  echo [dev] Backend API: http://localhost:8001
  exit /b 0
)

echo [dev] Starting React dev server with hot reload on http://localhost:3000 ...
cd frontend
set REACT_APP_API_URL=http://localhost:8001
call npm start
