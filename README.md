# JupyterHub 实训平台（Docker Compose 一键部署）

基于 Docker + JupyterHub 的多租户教学实训平台，包含：

- 前端门户（React）
- 实验管理后端（FastAPI + PostgreSQL + Redis）
- AI 助手服务（FastAPI，默认 DeepSeek，可选 Tavily 联网检索）
- JupyterHub（DockerSpawner：每位学生独立 Notebook 容器）
- 监控（Prometheus + Grafana）
- 统一入口网关（Nginx：`/` 前端、`/api` 后端、`/jupyter` Hub）

> 统一入口（本地）：`http://localhost:8080`  
> 统一入口（服务器）：`http://<服务器IP>/`  
> Hub 路径前缀：默认 `/jupyter`（同源反代，适合课堂/内网/公网）

---

## 1. 三种使用方式（先选一个）

| 目标 | 使用方式 | 入口 |
| --- | --- | --- |
| 本地完整运行（推荐） | `docker-compose.yml` 或 `start.bat` | `http://localhost:8080` |
| 前端热更新开发 | `start-dev.bat` | `http://localhost:3000` |
| Linux 服务器部署 | `docker-compose.server.yml` | `http://<服务器IP>/` |

---

## 2. 目录结构（核心）

```text
.
├── ai-service/                 # AI 助手服务（FastAPI）
├── backend/                    # 实验管理后端（FastAPI）
├── frontend/                   # 前端门户（React）
├── experiments/                # 课程与实验资源（会同步到 Docker 卷）
├── jupyterhub/                 # JupyterHub 配置（DockerSpawner）
├── monitoring/                 # Prometheus / Grafana 配置
├── nginx/                      # Nginx 配置（/api /jupyter 反代）
├── docker-compose.yml          # 本地完整模式
├── docker-compose.server.yml   # 服务器部署模式
├── start.bat                   # Windows 一键启动（完整模式）
├── start-dev.bat               # Windows 开发模式（前端热更新）
└── stop-dev.bat                # 停止开发模式后端容器
```

---

## 3. 前置要求

- Docker Desktop（Windows/Mac）或 Docker Engine（Linux）
- Docker Compose（`docker compose` 可用）
- Node.js 18+（仅开发模式需要）

---

## 4. 本地完整模式（推荐）

### 4.1 Windows 一键启动

在仓库根目录运行：

```bat
start.bat
```

脚本会构建镜像并启动容器，并在 `experiment-manager` 容器内执行 `python init_db.py` 初始化示例数据。

### 4.2 手动启动（跨平台）

```bash
docker compose up -d --build
```

首次启动建议执行一次初始化（可重复执行，已有数据会跳过）：

```bash
docker compose exec -T experiment-manager python init_db.py
```

### 4.3 本地访问地址

- 统一入口（推荐）：`http://localhost:8080`
- JupyterHub（经网关）：`http://localhost:8080/jupyter/`
- 后端 API 文档（直连容器端口）：`http://localhost:8001/docs`
- AI 助手 API 文档：`http://localhost:8002/docs`
- JupyterHub（直连端口）：`http://localhost:8003`
- Grafana：`http://localhost:3001`（默认 `admin/admin`）
- Prometheus：`http://localhost:9090`

### 4.4 停止

```bash
docker compose down
```

---

## 5. 开发模式（前端热更新）

> 开发模式会启动后端相关容器，停掉生产前端/网关，然后在本机启动 React dev server。

启动：

```bat
start-dev.bat
```

停止：

```bat
stop-dev.bat
```

只启动后端（不启动前端 dev server）：

```bat
set SKIP_FRONTEND=1 && start-dev.bat
```

开发模式入口：

- 前端：`http://localhost:3000`
- 后端 API：`http://localhost:8001`

更多说明见 `DEV_MODE.md`。

---

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

详细说明见 `DEPLOY_SERVER.md`。

---

## 7. 网关路由（Nginx）

平台通过 Nginx 做统一入口：

- `/` → 前端（React 静态站点）
- `/api/` → 后端（experiment-manager）
- `/jupyter/` → JupyterHub（支持 WebSocket，内核/终端/LSP）

网关支持将 `?token=...` 写入 Cookie，并桥接到 `Authorization`，便于浏览器同源访问 JupyterHub。

---

## 8. 账号与认证说明

### 8.1 门户/后端登录

- 登录接口：`POST /api/auth/login`
- 默认账号来源由环境变量配置：`ADMIN_ACCOUNTS`、`TEACHER_ACCOUNTS`
- 具体默认账号与密码请以后端初始化逻辑和当前配置为准

### 8.2 JupyterHub 登录（DummyAuthenticator）

- Hub 使用 `DummyAuthenticator`
- 若未设置 `DUMMY_PASSWORD`，Hub 可能允许任意密码登录（公网不安全）
- 公网部署务必设置 `DUMMY_PASSWORD`

---

## 9. 关键环境变量

推荐基于 `.env.server.example` 配置（服务器模式必用，本地模式也可用）：

- `DB_PASSWORD`：PostgreSQL 密码
- `EXPERIMENT_MANAGER_API_TOKEN`：后端调用 JupyterHub API 的服务 token
- `DUMMY_PASSWORD`：JupyterHub 共享登录口令
- `JUPYTERHUB_BASE_URL`：Hub 路径前缀（默认 `/jupyter`）
- `JUPYTERHUB_PUBLIC_URL`：后端返回给前端的 Hub 公网地址
- AI（可选）：
  - `DEEPSEEK_API_KEY` / `DEEPSEEK_BASE_URL` / `DEEPSEEK_MODEL`
  - `TAVILY_API_KEY`（联网检索）
  - `CACHE_TTL` / `MAX_HISTORY`

---

## 10. 数据与持久化（重要）

本项目默认使用 Docker volumes 持久化（重启/升级不丢数据）：

- `postgres-data`：PostgreSQL 数据
- `redis-data`：Redis 数据
- `jupyterhub-data`：JupyterHub 配置/密钥/运行状态
- `course-materials`：课程与实验资源（`data-loader` 从 `./experiments` 同步）

后端上传文件（资源/附件/提交 PDF）统一存储到 PostgreSQL（`BYTEA`）。

历史文件迁移到 PG（一次性）：

```bash
cd backend
python -m app.scripts.migrate_file_blobs_to_pg
# 如需迁移后删除旧磁盘文件：
python -m app.scripts.migrate_file_blobs_to_pg --delete-source
```

---

## 11. 常用命令

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

初始化示例实验数据：

```bash
docker compose exec -T experiment-manager python init_db.py
```

---

## 12. 常见问题（FAQ）

### 12.1 端口冲突

本地完整模式至少需要端口：`8080`、`8001`、`8002`、`8003`、`3001`、`9090`。  
开发模式还需要：`3000`。

### 12.2 访问 `/jupyter` 白屏或内核无法连接

- 确保走网关：`http://localhost:8080/jupyter/`（而不是直连 `8003`）
- 确保 Nginx 对 WebSocket 的反代已启用（本仓库已配置）

### 12.3 服务器上 AI/监控默认打不开

服务器 compose 默认将 AI / Prometheus / Grafana 端口绑定到 `127.0.0.1`，适合通过 SSH 隧道访问。若需公网开放，请修改 `docker-compose.server.yml` 的端口绑定。

---

## 13. 技术栈

- Frontend: React + axios + react-router-dom
- Backend: FastAPI + SQLAlchemy + Alembic + asyncpg/psycopg2 + Redis
- Hub: JupyterHub + DockerSpawner
- Proxy: Nginx
- Observability: Prometheus + Grafana
- AI: DeepSeek Chat Completions（可选 Tavily web search）
