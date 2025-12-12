# 部署目录

本目录包含所有部署相关的脚本和配置文件。

## 📁 文件说明

### 核心部署脚本

- **`deploy.sh`** - 主部署脚本，用于从本地部署到远程服务器
  - 使用方法：`./deploy/deploy.sh` 或 `cd deploy && ./deploy.sh`
  - 功能：上传项目文件、执行服务器端部署脚本

- **`server_deploy.sh`** - 服务器端部署脚本，在远程服务器上执行
  - 功能：安装依赖、构建前端、启动服务

- **`setup_nginx.sh`** - Nginx配置脚本，在服务器上运行
  - 功能：自动配置nginx，创建独立的配置文件（`investment-agent.conf`），不影响现有服务
  - 使用方法：在服务器上运行 `bash deploy/setup_nginx.sh` 或 `cd deploy && ./setup_nginx.sh`
  - 特点：使用独立的配置文件，不会覆盖或影响服务器上已有的nginx配置

### 配置文件

- **`.deploy.env.example`** - 部署配置示例文件
  - 复制到项目根目录为 `.deploy.env` 并填写实际配置
  - 命令：`cp deploy/.deploy.env.example .deploy.env`

- **`nginx.conf.example`** - Nginx配置示例文件
  - 请手动复制并修改为实际配置

### 文档

- **`DEPLOYMENT_CHECKLIST.md`** - 部署前检查清单和常见问题
- **`FRONTEND_PATH_CONFIG.md`** - 前端路径配置说明
- **`NGINX_CONFIG_GUIDE.md`** - Nginx配置详细指南

## 🚀 快速开始

### 1. 准备配置文件

```bash
# 从示例文件创建配置
cp deploy/.deploy.env.example .deploy.env

# 编辑配置文件
vim .deploy.env
```

### 2. 执行部署

```bash
# 方式1：从项目根目录执行
./deploy/deploy.sh

# 方式2：进入deploy目录执行
cd deploy
./deploy.sh
```

## 📋 配置说明

`.deploy.env` 文件需要配置以下内容：

```bash
# 服务器配置
SERVER_HOST=your-server-ip
SERVER_USER=root
DEPLOY_PATH=/opt/investment_agent

# 端口配置
FRONTEND_PORT=8100
BACKEND_PORT=8101

# SSH配置
SERVER_PASSWORD=your-password
# 或使用密钥认证
# SSH_KEY_PATH=~/.ssh/id_rsa
SSH_PORT=22
```

## 📝 注意事项

1. **`.deploy.env` 文件位置**：
   - 配置文件 `.deploy.env` 应该放在**项目根目录**，而不是 `deploy` 目录
   - 该文件已在 `.gitignore` 中，不会被提交到版本控制

2. **部署脚本路径**：
   - `deploy.sh` 会自动检测项目根目录
   - 确保从项目根目录或 `deploy` 目录执行脚本

3. **服务器端文件**：
   - `server_deploy.sh` 和 `nginx.conf.example` 会被上传到服务器
   - 服务器上的部署路径应该包含这些文件

## 🔍 故障排查

如果遇到问题，请参考：
- `DEPLOYMENT_CHECKLIST.md` - 详细的检查清单

## 📚 相关文档

- 项目根目录的 `README.md` - 项目总体说明
