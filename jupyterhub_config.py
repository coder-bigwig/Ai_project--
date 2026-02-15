# jupyterhub_config.py - JupyterHub配置文件

import os
import sys

# ==================== 基础配置 ====================

# JupyterHub 绑定地址和端口
c.JupyterHub.bind_url = 'http://0.0.0.0:8000'

# 数据库连接（使用PostgreSQL）
c.JupyterHub.db_url = 'postgresql://jupyterhub:password@localhost/jupyterhub'

# 管理员用户列表
c.Authenticator.admin_users = {'admin', 'teacher1', 'teacher2'}

# 允许管理员访问用户的notebook
c.JupyterHub.admin_access = True

# ==================== 用户认证配置 ====================

# 使用自定义认证器（可以对接现有用户系统）
# c.JupyterHub.authenticator_class = 'oauthenticator.generic.GenericOAuthenticator'

# 或使用本地认证（开发测试用）
from jupyterhub.auth import DummyAuthenticator
c.JupyterHub.authenticator_class = DummyAuthenticator

# ==================== Docker容器配置 ====================

c.JupyterHub.spawner_class = 'dockerspawner.DockerSpawner'

# 使用的Docker镜像
c.DockerSpawner.image = 'training-lab:latest'

# 容器名称模板
c.DockerSpawner.name_template = 'jupyter-{username}'

# 容器启动后自动删除
c.DockerSpawner.remove = True

# Docker网络配置
c.DockerSpawner.network_name = 'jupyterhub-network'
c.DockerSpawner.use_internal_ip = True

# ==================== 资源限制配置 ====================

# CPU限制（核心数）
c.DockerSpawner.cpu_limit = 2.0  # 最多2核
c.DockerSpawner.cpu_guarantee = 0.5  # 保证0.5核

# 内存限制
c.DockerSpawner.mem_limit = '4G'  # 最多4GB
c.DockerSpawner.mem_guarantee = '1G'  # 保证1GB

# ==================== 存储卷配置 ====================

# 定义notebook挂载函数（为每个用户创建独立存储）
def create_volume_mounts(spawner):
    username = spawner.user.name
    
    volumes = {
        # 用户工作目录（持久化）
        f'jupyterhub-user-{username}': {
            'bind': '/home/jovyan/work',
            'mode': 'rw'
        },
        # 共享数据集目录（只读）
        '/opt/shared-datasets': {
            'bind': '/home/jovyan/datasets',
            'mode': 'ro'
        },
        # 实验模板目录（只读）
        '/opt/experiment-templates': {
            'bind': '/home/jovyan/templates',
            'mode': 'ro'
        }
    }
    
    return volumes

c.DockerSpawner.volumes = create_volume_mounts

# ==================== 环境变量配置 ====================

def set_environment(spawner):
    """为每个用户设置环境变量"""
    env = {
        'JUPYTER_ENABLE_LAB': '1',  # 启用JupyterLab
        'GRANT_SUDO': 'no',  # 禁止sudo权限
        'USER': spawner.user.name,
        'STUDENT_ID': spawner.user.name,
        # AI API配置（如果使用）
        'AI_API_ENDPOINT': 'http://ai-service:8080',
        # 实验管理API
        'EXPERIMENT_API': 'http://experiment-manager:8000',
    }
    return env

c.DockerSpawner.environment = set_environment

# ==================== 用户自定义配置 ====================

# 根据用户角色设置不同的资源配置
def customize_spawner(spawner):
    """根据用户角色定制spawner配置"""
    username = spawner.user.name
    
    # 教师账号获得更多资源
    if username.startswith('teacher') or spawner.user.admin:
        spawner.cpu_limit = 4.0
        spawner.mem_limit = '8G'
        spawner.image = 'training-lab:teacher-edition'
    
    # 学生账号标准配置
    else:
        spawner.cpu_limit = 2.0
        spawner.mem_limit = '4G'
        spawner.image = 'training-lab:student-edition'
    
    return spawner

c.Spawner.pre_spawn_hook = customize_spawner

# ==================== 安全配置 ====================

# 禁用用户自定义镜像
c.DockerSpawner.allowed_images = ['training-lab:latest']

# 容器运行用户（非root）
c.DockerSpawner.container_user = 'jovyan'

# 只读根文件系统（除挂载目录外）
# c.DockerSpawner.read_only = True

# 禁用特权模式
c.DockerSpawner.privileged = False

# 资源清理：用户停止后自动删除容器
c.DockerSpawner.remove = True

# ==================== 超时配置 ====================

# 启动超时（秒）
c.Spawner.start_timeout = 300

# 超过指定时间未活动则自动停止（秒，0表示禁用）
c.Spawner.timeout = 3600  # 1小时无活动自动停止

# HTTP超时
c.Spawner.http_timeout = 120

# ==================== 服务配置 ====================

# 添加自定义服务
c.JupyterHub.services = [
    {
        'name': 'experiment-manager',
        'url': 'http://127.0.0.1:8001',
        'api_token': 'secret-token-for-service',
        'admin': True
    },
    {
        'name': 'ai-assistant',
        'url': 'http://127.0.0.1:8002',
        'api_token': 'secret-token-for-ai',
    }
]

# ==================== 日志配置 ====================

c.JupyterHub.log_level = 'INFO'
c.Spawner.debug = True

# 日志文件
c.JupyterHub.extra_log_file = '/var/log/jupyterhub.log'

# ==================== 代理配置 ====================

# 使用ConfigurableHTTPProxy
c.ConfigurableHTTPProxy.should_start = True
c.ConfigurableHTTPProxy.auth_token = 'super-secret-proxy-token'

# ==================== 并发限制 ====================

# 同时运行的最大用户数
c.JupyterHub.concurrent_spawn_limit = 10

# 每个用户的活动服务器数量限制
c.JupyterHub.active_server_limit = 1

# ==================== 自定义页面 ====================

# 自定义模板目录
c.JupyterHub.template_paths = ['/opt/jupyterhub-templates']

# 自定义静态文件目录
c.JupyterHub.extra_static_paths = ['/opt/jupyterhub-static']

# 自定义Logo
c.JupyterHub.logo_file = '/opt/jupyterhub-static/logo.png'

# ==================== API配置 ====================

# 启用API访问
c.JupyterHub.api_tokens = {
    'secret-api-token-1': 'admin',  # 管理员token
    'secret-api-token-2': 'service-account',  # 服务账号token
}

# ==================== 健康检查 ====================

# Hub健康检查URL
c.JupyterHub.hub_health_check_interval = 60

# ==================== 数据库备份配置 ====================

# 定期备份用户数据（通过外部脚本）
c.JupyterHub.load_roles = [
    {
        'name': 'teacher',
        'description': '教师角色',
        'scopes': [
            'admin:users',  # 管理用户
            'admin:servers',  # 管理服务器
            'list:users',  # 查看用户列表
            'read:users:activity',  # 查看用户活动
        ],
        'users': ['teacher1', 'teacher2'],
    },
    {
        'name': 'student',
        'description': '学生角色',
        'scopes': [
            'self',  # 只能访问自己的资源
        ],
    }
]

# ==================== 实验环境特定配置 ====================

# 代码执行超时（通过notebook扩展实现）
c.DockerSpawner.environment = {
    **c.DockerSpawner.environment,
    'CODE_EXECUTION_TIMEOUT': '60',  # 单个cell执行超时60秒
    'MAX_OUTPUT_LENGTH': '10000',  # 输出最大长度
}

# ==================== 监控和指标 ====================

# Prometheus指标端点
c.JupyterHub.authenticate_prometheus = False
c.JupyterHub.enable_prometheus_metrics = True

# ==================== 自定义启动脚本 ====================

c.Spawner.cmd = ['jupyterhub-singleuser']

# 在用户环境中执行的初始化脚本
c.DockerSpawner.extra_create_kwargs = {
    'labels': {
        'traefik.enable': 'true',
        'app': 'jupyterhub-training-platform'
    }
}

# ==================== 调试模式（生产环境应关闭）====================

# c.JupyterHub.debug_proxy = True
# c.DockerSpawner.debug = True
# c.JupyterHub.log_level = 'DEBUG'

print("=" * 60)
print("JupyterHub 实训平台配置已加载")
print(f"Spawner: {c.JupyterHub.spawner_class}")
print(f"镜像: {c.DockerSpawner.image}")
print(f"CPU限制: {c.DockerSpawner.cpu_limit} 核")
print(f"内存限制: {c.DockerSpawner.mem_limit}")
print("=" * 60)
