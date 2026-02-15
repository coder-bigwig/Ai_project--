@echo off
setlocal

cd /d %~dp0

echo [dev] Stopping dev backend containers...
docker stop training-experiment-manager training-ai-assistant training-redis training-postgres >nul 2>&1

echo [dev] Optional: return to production gateway with:
echo        docker compose up -d frontend nginx
echo [dev] Done.
