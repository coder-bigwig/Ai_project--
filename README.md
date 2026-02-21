# JupyterHub 实训平台

基于 Docker + JupyterHub 的多租户教学实训平台，包含：

- 前端门户（React）
- 实验管理后端（FastAPI）
- AI 助手服务（FastAPI，默认 DeepSeek，可选 Tavily）
- JupyterHub（DockerSpawner，多租户）
- 监控（Prometheus + Grafana）

## 1. 先看这里：三种使用方式

| 目标 | 使用方式 | 入口 |
| --- | --- | --- |
| 本地完整运行（最常用） | `docker-compose.yml` 或 `start.bat` | `http://localhost:8080` |
| 前端热更新开发 | `start-dev.bat` | `http://localhost:3000` |
| Linux 服务器部署 | `docker-compose.server.yml` | `http://<服务器IP>/` |

## 2. 目录结构

```text
.
├── ai-service/                 # AI 助手服务
├── backend/                    # 实验管理后端
├── frontend/                   # 前端门户
├── experiments/                # 课程与实验资源
├── jupyterhub/                 # JupyterHub 配置
├── monitoring/                 # Prometheus / Grafana 配置
├── nginx/                      # Nginx 配置
├── docker-compose.yml          # 本地完整模式
├── docker-compose.server.yml   # 服务器部署模式
├── start.bat                   # Windows 一键启动（完整模式）
├── start-dev.bat               # Windows 开发模式（前端热更新）
└── stop-dev.bat                # 停止开发模式后端容器
```

## 3. 前置要求

- Docker Desktop（Windows/Mac）或 Docker Engine（Linux）
- Docker Compose（`docker compose` 可用）
- Node.js 18+（仅前端开发模式需要）

## 4. 本地完整模式（推荐先跑这个）

### 4.1 Windows 一键启动

在仓库根目录运行：

```bat
start.bat
```

该脚本会自动执行：

1. 构建镜像
2. 启动容器
3. 等待服务就绪
4. 在 `experiment-manager` 容器内执行 `python init_db.py`

### 4.2 手动启动（跨平台）

```bash
docker compose up -d --build
```

如果你是第一次手动启动，建议再执行一次初始化：

```bash
docker compose exec -T experiment-manager python init_db.py
```

### 4.3 本地访问地址

- 统一入口（推荐）：`http://localhost:8080`
- JupyterHub（经网关）：`http://localhost:8080/jupyter/`
- 后端 API 文档（直连后端容器端口）：`http://localhost:8001/docs`
- AI 助手 API 文档：`http://localhost:8002/docs`
- JupyterHub（直连端口）：`http://localhost:8003`
- Grafana：`http://localhost:3001`（默认 `admin/admin`）
- Prometheus：`http://localhost:9090`

### 4.4 停止

```bash
docker compose down
```

## 5. 开发模式（前端热更新）

说明：`start-dev.bat` 会启动后端容器，并停止生产前端/网关容器，然后在本机启动 React dev server。

启动：

```bat
start-dev.bat
```

停止开发模式后端容器：

```bat
stop-dev.bat
```

只启动后端，不启动前端 dev server：

```bat
set SKIP_FRONTEND=1 && start-dev.bat
```

开发模式入口：

- 前端：`http://localhost:3000`
- 后端 API：`http://localhost:8001`

更多说明见 `DEV_MODE.md`。

## 6. 服务器部署模式（Linux）

快速步骤：

```bash
cp .env.server.example .env
docker compose -f docker-compose.server.yml up -d --build
```

常用检查：

```bash
docker compose -f docker-compose.server.yml ps
docker compose -f docker-compose.server.yml logs -f nginx
```

默认入口：

- 门户：`http://<服务器IP>/`
- JupyterHub：`http://<服务器IP>/jupyter/`

详细部署、安全和 HTTPS 说明见 `DEPLOY_SERVER.md`。

## 7. 账号与认证说明（重要）

- 门户/API 登录接口：`POST /api/auth/login`
- 后端默认账号来源：
  - 管理员：`ADMIN_ACCOUNTS`（默认 `admin`）
  - 教师：`TEACHER_ACCOUNTS`（默认 `teacher_001` 到 `teacher_005`）
- 默认密码：`123456`（建议首次登录后修改）
- 学生账号来自用户注册数据（导入或已有持久化）
- JupyterHub 使用 `DummyAuthenticator`：
  - 若未设置 `DUMMY_PASSWORD`，Hub 登录可使用任意密码
  - 公网部署务必设置 `DUMMY_PASSWORD`

## 8. 关键环境变量

推荐基于 `.env.server.example` 配置：

- `DB_PASSWORD`：PostgreSQL 密码
- `EXPERIMENT_MANAGER_API_TOKEN`：后端调用 JupyterHub API 的服务 token
- `DUMMY_PASSWORD`：JupyterHub 共享登录口令（强烈建议设置）
- `JUPYTERHUB_BASE_URL`：Hub 路径前缀（默认 `/jupyter`）
- `JUPYTERHUB_PUBLIC_URL`：后端返回给前端的 Hub 公网地址（默认 `/jupyter`）
- `DEEPSEEK_API_KEY` / `DEEPSEEK_BASE_URL` / `DEEPSEEK_MODEL`：AI 模型配置
- `TAVILY_API_KEY`：联网检索能力（可选）

## 9. 常用命令

本地完整模式：

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f experiment-manager
docker compose down
```

服务器模式：

```bash
docker compose -f docker-compose.server.yml up -d --build
docker compose -f docker-compose.server.yml ps
docker compose -f docker-compose.server.yml logs -f nginx
docker compose -f docker-compose.server.yml down
```

## 10. 常见问题

### 10.1 端口冲突

本地完整模式至少需要这些端口可用：`8080`、`8001`、`8002`、`8003`、`3001`、`9090`。  
开发模式还需要 `3000`。

### 10.2 `start-dev.bat` 启动失败

- 脚本会先尝试 `docker start` 既有容器，不存在时自动回退到 `docker compose up`。
- 若仍失败，先执行一次 `start.bat` 完成初始构建，再运行 `start-dev.bat`。

### 10.3 AI 助手不可用

- 检查 `DEEPSEEK_API_KEY` 是否正确配置。
- 查看日志：`docker compose logs -f ai-assistant`。

### 10.4 公网部署安全

- 必须设置强密码（`DB_PASSWORD`、`DUMMY_PASSWORD`、`EXPERIMENT_MANAGER_API_TOKEN`）。
- 建议启用 HTTPS 反向代理。

## PostgreSQL-only storage mode (2026-02)

- Runtime storage backend is fixed to PostgreSQL.
- App startup will fail fast when PostgreSQL is unavailable (no JSON fallback).

### Data initialization

- `backend/init_db.py` is a seed script. It seeds data by calling backend APIs, and data is persisted into PostgreSQL tables.
- Typical flow in Docker:
  1. `docker compose up -d --build`
  2. `docker compose exec -T experiment-manager python init_db.py`

## PostgreSQL Runtime Notes (2026-02-21)

- Runtime authority is PostgreSQL only. `state.py` dicts are no longer used as business source of truth.
- FastAPI startup only does DB connectivity check + schema creation (`create_all`); it does not auto-seed sample business data.
- JupyterHub resource quota policy is read from PostgreSQL key `app_kv_store.resource_policy` (not JSON file).
- PostgreSQL self-check script:
  - `docker compose exec -T experiment-manager python -m app.scripts.postgres_self_check`
