# JupyterHub 实训平台

基于 Docker + JupyterHub 的多租户实训平台，包含实验管理后端、前端门户、AI 助手服务与监控组件。

## 项目状态（当前仓库）

- 前端为 React（`react-scripts`），不是 Vite。
- AI 助手默认对接 DeepSeek（可选 Tavily 检索），不是默认本地 Ollama。
- 本地完整模式通过 `docker-compose.yml` 启动，入口为 `http://localhost:8080`。
- 前端开发热更新模式通过 `start-dev.bat` 启动，入口为 `http://localhost:3000`。

## 目录结构

```text
.
├── ai-service/                 # AI 助手服务（FastAPI）
├── backend/                    # 实验管理后端（FastAPI）
├── frontend/                   # 前端门户（React + react-scripts）
├── experiments/                # 实验与课程资源
├── jupyterhub/                 # JupyterHub 配置
├── monitoring/                 # Prometheus / Grafana 配置
├── nginx/                      # Nginx 配置
├── docker-compose.yml          # 本地完整模式
├── docker-compose.server.yml   # 服务器部署模式
├── start.bat                   # Windows 一键启动（完整模式）
├── start-dev.bat               # Windows 开发模式（前端热更新）
└── stop-dev.bat                # 停止开发模式后端容器
```

## 技术栈

- 核心：Docker, JupyterHub, DockerSpawner, Python
- 前端：React 18, `react-scripts`, `react-router-dom`, `axios`
- 后端：FastAPI
- AI：DeepSeek API（`DEEPSEEK_*`），可选 Tavily（`TAVILY_API_KEY`）
- 监控：Prometheus, Grafana
- 基础服务容器：PostgreSQL, Redis, Nginx

## 快速开始（本地完整模式）

### 前置要求

- Docker Desktop（Windows/Mac/Linux）
- Windows 用户建议直接使用 `start.bat`

### 启动方式 A（推荐，Windows）

在仓库根目录双击运行：

```bat
start.bat
```

脚本会执行：

1. `docker-compose build`
2. `docker-compose up -d`
3. 等待服务就绪
4. 在 `experiment-manager` 容器中执行 `python init_db.py`

### 启动方式 B（手动）

```bash
docker compose up -d --build
```

### 本地访问地址

- 统一入口（Nginx）：`http://localhost:8080`
- 实验管理 API 文档：`http://localhost:8001/docs`
- AI 助手 API 文档：`http://localhost:8002/docs`
- JupyterHub：`http://localhost:8003`
- Grafana：`http://localhost:3001`（默认 `admin/admin`）
- Prometheus：`http://localhost:9090`

## 开发模式（前端热更新）

开发模式说明见 `DEV_MODE.md`。核心行为如下：

1. 启动后端相关容器（`postgres`/`redis`/`experiment-manager`/`ai-assistant`）
2. 停止生产前端网关容器（`training-frontend`/`training-nginx`）
3. 在本机启动 React dev server（`http://localhost:3000`）

启动：

```bat
start-dev.bat
```

停止（仅停止开发模式后端容器）：

```bat
stop-dev.bat
```

仅调后端（不启动前端 dev server）：

```bat
set SKIP_FRONTEND=1 && start-dev.bat
```

## 账号与权限说明

- JupyterHub 认证使用 `DummyAuthenticator`。
- 若未设置 `DUMMY_PASSWORD`，JupyterHub 层面可使用任意密码登录（不建议在公网环境保持默认）。
- 门户/API 登录由后端 `/api/auth/login` 控制，不是简单“用户名前缀判断”。
- 默认角色账号来自环境变量：
  - `ADMIN_ACCOUNTS`（默认 `admin`）
  - `TEACHER_ACCOUNTS`（默认 `teacher_001,teacher_002,teacher_003,teacher_004,teacher_005`）
- 以上账号默认密码为 `123456`（建议首次登录后修改）。
- 学生账号来自用户注册表数据（导入或已有持久化数据）。

## 关键环境变量

服务器部署可参考 `.env.server.example`（复制为 `.env`）：

- `DB_PASSWORD`
- `EXPERIMENT_MANAGER_API_TOKEN`
- `DUMMY_PASSWORD`
- `JUPYTERHUB_BASE_URL`
- `JUPYTERHUB_PUBLIC_URL`
- `DEEPSEEK_API_KEY`
- `DEEPSEEK_BASE_URL`
- `DEEPSEEK_MODEL`
- `TAVILY_API_KEY`

## 服务器部署

使用 `docker-compose.server.yml`，详细说明见 `DEPLOY_SERVER.md`。

典型流程：

```bash
cp .env.server.example .env
docker compose -f docker-compose.server.yml up -d --build
```

## 常用命令

启动全部服务：

```bash
docker compose up -d --build
```

查看状态：

```bash
docker compose ps
```

查看后端日志：

```bash
docker compose logs -f experiment-manager
```

停止并移除容器：

```bash
docker compose down
```

## 常见问题

### 1) 端口冲突

本地完整模式需确保以下端口可用：`8080`、`8001`、`8002`、`8003`、`3001`、`9090`。  
开发模式还需要 `3000`。

### 2) `start-dev.bat` 启动失败

首次运行时若后端容器不存在，脚本会回退到 `docker compose up`。若仍失败，先执行一次 `start.bat` 拉取并构建基础镜像。

### 3) 公网部署安全性

请务必设置强口令与 `DUMMY_PASSWORD`，并按需启用 HTTPS 反向代理。
