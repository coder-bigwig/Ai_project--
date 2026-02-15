# 服务器部署（Docker Compose）

本项目已提供服务器部署专用的编排文件 `docker-compose.server.yml`，特性如下：

- 统一对外只暴露 1 个入口：Nginx（默认 `:80`）
- JupyterHub 走同源路径：`/jupyter/*`（多租户：每个学生独立容器 + 独立持久化卷）
- 后端 API：`/api/*`
- Postgres/Redis 仅容器内网访问
- Prometheus/Grafana/AI 默认仅绑定在 `127.0.0.1`（需要可改成对外端口或走 SSH 隧道）

## 1. 服务器前置要求

- Linux 服务器（建议 Ubuntu 20.04+/Debian 11+）
- 已安装 Docker Engine 与 Docker Compose 插件（`docker compose` 可用）
- 服务器安全组/防火墙放行端口：`80`（如果你做 HTTPS，再放行 `443`）

## 2. 部署步骤

在服务器上执行：

```bash
git clone https://github.com/coder-bigwig/Ai_project2.8.git
cd Ai_project2.8
cp .env.server.example .env
```

编辑 `.env`，至少要改这 3 项：

- `DB_PASSWORD`：数据库密码
- `EXPERIMENT_MANAGER_API_TOKEN`：后端调用 JupyterHub API 的 token（建议 32 位以上随机字符串）
- `DUMMY_PASSWORD`：建议设置（不然 JupyterHub 任意用户名 + 任意密码都能登录，风险很高）

启动：

```bash
docker compose -f docker-compose.server.yml up -d --build
```

查看运行状态：

```bash
docker compose -f docker-compose.server.yml ps
docker compose -f docker-compose.server.yml logs -f nginx
```

## 3. 访问地址

假设你的服务器公网 IP 为 `x.x.x.x`：

- 平台门户：`http://x.x.x.x/`
- JupyterHub：`http://x.x.x.x/jupyter/`
- 后端接口文档：`http://x.x.x.x/api/docs`

## 4. 多租户说明（每个学生都不一样，属于多租户）

当前 JupyterHub 为 **多租户模式**：

- 每个用户启动时由 `DockerSpawner` 创建一个独立容器
- 每个用户有独立持久化卷：`training-user-{username}` 挂载到容器 `/home/jovyan/work`
- 公共只读课件：`training-course-materials` 挂载到 `/home/jovyan/course`
- 公共只读数据集：`training-shared-datasets` 挂载到 `/home/jovyan/datasets`

## 5. 常用运维命令

升级（拉代码后重建）：

```bash
git pull
docker compose -f docker-compose.server.yml up -d --build
```

停止：

```bash
docker compose -f docker-compose.server.yml down
```

查看卷（注意不要随意删除）：

```bash
docker volume ls | grep training-
```

## 6. HTTPS（可选）

建议在公网环境启用 HTTPS（尤其是账号密码、token 相关）。

你可以：

1. 用宿主机 Nginx/Apache/Caddy 做 TLS 终止，然后反代到容器 `training-nginx:80`
2. 或者给容器内 Nginx 配证书（需要自己挂载证书文件并改 `nginx.server.conf`）

如果你告诉我服务器系统、是否有域名、是否要用 443，我可以再给你补一套“自动签发证书”的部署文件（例如 Caddy/Certbot）。

