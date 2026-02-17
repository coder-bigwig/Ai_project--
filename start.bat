@echo off
setlocal

cd /d %~dp0
chcp 65001 >nul
set PYTHONUTF8=1

echo ========================================================
echo       JupyterHub 实训平台 - 一键启动脚本
echo ========================================================
echo.

:: 检查 Docker 是否运行
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] Docker 未运行或未安装。请先启动 Docker Desktop。
    pause
    exit /b
)

echo [1/4] 构建 Docker 镜像...
docker-compose build
if %errorlevel% neq 0 (
    echo [错误] 镜像构建失败。
    pause
    exit /b
)

echo.
echo [2/4] 启动服务...
docker-compose up -d
if %errorlevel% neq 0 (
    echo [错误] 服务启动失败。
    pause
    exit /b
)

echo.
echo [3/4] 等待服务初始化 (约 30 秒)...
timeout /t 30 /nobreak >nul

echo.
echo [4/4] 初始化数据库和示例数据...
:: 这里我们通过执行后端容器中的脚本来初始化数据
docker-compose exec -T experiment-manager python init_db.py

echo.
echo ========================================================
echo               部署完成！
echo ========================================================
echo.
echo 请访问以下地址：
echo.
echo   - 统一入口: http://localhost:8080
echo   - 实验管理 API: http://localhost:8001/docs
echo   - AI 助手 API: http://localhost:8002/docs
echo   - 监控面板 (Grafana): http://localhost:3001 (admin/admin)
echo.
echo 按任意键关闭此窗口...
pause >nul
