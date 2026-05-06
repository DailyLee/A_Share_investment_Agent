# 服务冲突问题解决方案

## 问题描述

当启动一个 Python 服务（8101端口）时，另一个服务（8001端口）会挂掉。

## 根本原因

### 1. **共享的全局单例对象**

代码中存在多个全局单例，如果两个服务运行在同一个 Python 进程或共享相同的模块导入，会导致冲突：

- `backend.main.app` - FastAPI 应用实例（全局单例）
- `backend.state.api_state` - API 状态管理（全局单例）
- `backend.dependencies.get_log_storage()` - 日志存储（可能返回单例）

### 2. **Systemd 服务配置冲突**

如果两个服务使用：
- 相同的 systemd 服务名称
- 相同的工作目录
- 相同的环境变量

可能导致资源冲突。

### 3. **端口绑定问题**

虽然端口不同（8001 vs 8101），但如果服务配置错误，可能会尝试绑定到已占用的端口。

## 解决方案

### 方案 1: 使用不同的 Systemd 服务名称（推荐）

为每个服务创建独立的 systemd 服务文件：

**服务 1 (8001端口):**
```ini
[Unit]
Description=Stock Scanner Backend Service (Port 8001)
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/investment_agent
Environment="PATH=/usr/local/bin:/usr/bin:/bin"
ExecStart=/usr/local/bin/poetry run python run_with_backend.py --backend-port 8001
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**服务 2 (8101端口):**
```ini
[Unit]
Description=Stock Scanner Backend Service (Port 8101)
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/investment_agent
Environment="PATH=/usr/local/bin:/usr/bin:/bin"
ExecStart=/usr/local/bin/poetry run python run_with_backend.py --backend-port 8101
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**创建服务文件：**
```bash
# 服务 1
sudo cp stock-scanner-8001.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable stock-scanner-8001.service
sudo systemctl start stock-scanner-8001.service

# 服务 2
sudo cp stock-scanner-8101.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable stock-scanner-8101.service
sudo systemctl start stock-scanner-8101.service
```

### 方案 2: 使用不同的工作目录

如果两个服务必须使用不同的配置，可以使用不同的工作目录：

```ini
[Service]
WorkingDirectory=/opt/investment_agent_8001  # 服务 1
# 或
WorkingDirectory=/opt/investment_agent_8101  # 服务 2
```

### 方案 3: 使用环境变量隔离

在 systemd 服务文件中设置不同的环境变量：

```ini
[Service]
Environment="SERVICE_PORT=8001"
Environment="SERVICE_NAME=service_8001"
Environment="LOG_DIR=/var/log/investment_agent_8001"
```

### 方案 4: 代码层面隔离（长期解决方案）

修改代码以支持多实例运行，避免全局单例：

1. **创建应用工厂函数**：
```python
# backend/main.py
def create_app():
    app = FastAPI(
        title="A Share Investment Agent - Backend",
        description="API for monitoring LLM interactions within the agent workflow.",
        version="0.1.0"
    )
    # ... 配置路由等
    return app

# 默认导出
app = create_app()
```

2. **状态管理支持多实例**：
```python
# backend/state.py
class ApiState:
    def __init__(self, instance_id: str = "default"):
        self.instance_id = instance_id
        # ... 其他初始化

# 使用实例ID区分不同服务
api_state = ApiState(instance_id=os.getenv("SERVICE_INSTANCE_ID", "default"))
```

## 诊断步骤

1. **运行诊断脚本**：
```bash
bash deploy/diagnose_service_conflict.sh
```

2. **检查服务状态**：
```bash
sudo systemctl status stock-scanner.service
sudo journalctl -u stock-scanner.service -n 50
```

3. **检查端口占用**：
```bash
sudo ss -tlnp | grep -E "8001|8101"
```

4. **检查进程**：
```bash
ps aux | grep -E "python.*run_with_backend|uvicorn"
```

## 临时解决方案

如果问题紧急，可以：

1. **停止冲突的服务**：
```bash
sudo systemctl stop stock-scanner.service
```

2. **检查并修改服务配置**：
```bash
sudo cat /etc/systemd/system/stock-scanner.service
```

3. **确保端口不同**：
在 `.deploy.env` 中明确设置：
```bash
BACKEND_PORT=8101  # 确保与另一个服务不同
```

4. **重启服务**：
```bash
sudo systemctl daemon-reload
sudo systemctl restart stock-scanner.service
```

## 最佳实践

1. **每个服务使用独立的 systemd 服务名称**
2. **使用环境变量区分不同实例**
3. **避免共享全局状态（如果可能）**
4. **使用不同的日志文件路径**
5. **监控服务健康状态**

## 相关文件

- `deploy/diagnose_service_conflict.sh` - 诊断脚本
- `deploy/server_deploy.sh` - 部署脚本
- `run_with_backend.py` - 服务启动脚本
- `/etc/systemd/system/stock-scanner.service` - Systemd 服务配置

