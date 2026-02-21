# 服务器部署（Docker Compose）

本项目已提供服务器部署专用编排文件：`docker-compose.server.yml`，特性如下：

- 对外只暴露 1 个入口：Nginx（默认 `:80`，可改）
- 同源路径代理：
  - 门户：`/`
  - 后端 API：`/api/*`
  - JupyterHub：`/jupyter/*`
- Postgres / Redis 仅容器内网访问（不对公网暴露）
- Prometheus / Grafana / AI Assistant 默认仅绑定 `127.0.0.1`（建议通过 SSH 隧道访问）

> 注意：运行态存储后端已固定为 PostgreSQL（PG-only）。线上必须确保 PG 可用，否则服务会启动失败（不会回退到 JSON）。

---

## 1. 服务器前置要求

- Linux 服务器（建议 Ubuntu 20.04+/Debian 11+）
- 已安装 Docker Engine + Docker Compose 插件（确保 `docker compose` 可用）
- 防火墙/安全组放行端口：
  - HTTP：`80`
  - 如启用 HTTPS：再放行 `443`

---

## 2. 部署步骤

### 2.1 拉取代码 & 配置环境变量

在服务器上执行：

```bash
git clone https://github.com/coder-bigwig/Ai_project-2026-2-20-23.35.git
cd Ai_project-2026-2-20-23.35
cp .env.server.example .env
