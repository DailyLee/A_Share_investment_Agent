# 部署前检查清单

## ✅ 已修复的问题

### 1. SSH认证问题
- ✅ 修复了 `deploy.sh` 中缺失的 `ssh_with_password.sh` 引用
- ✅ 添加了fallback机制，如果expect脚本不存在，会尝试使用sshpass

### 2. Poetry虚拟环境路径
- ✅ 修复了systemd服务文件中的虚拟环境路径问题
- ✅ 添加了自动检测Poetry虚拟环境路径的逻辑
- ✅ 如果找不到虚拟环境，依赖 `poetry run` 来管理环境

### 3. 部署路径一致性
- ✅ 修复了nginx配置中的路径替换逻辑
- ✅ 支持替换 `/opt/stock-scanner` 和 `/opt/investment_agent` 为实际DEPLOY_PATH
- ✅ 确保所有路径配置都从 `.deploy.env` 读取

### 4. 前端构建验证
- ✅ 添加了前端构建后的验证（检查dist目录是否存在）
- ✅ 添加了nginx配置测试前的dist目录检查

### 5. 错误处理
- ✅ 改进了错误提示信息
- ✅ 添加了更详细的日志输出

## 📋 部署前检查项

### 配置文件检查
- [ ] 确认 `.deploy.env` 文件存在且配置正确
- [ ] 确认 `SERVER_HOST`、`SERVER_USER`、`DEPLOY_PATH` 已填写
- [ ] 确认 `FRONTEND_PORT` 和 `BACKEND_PORT` 已设置且未被占用
- [ ] 确认 `SERVER_PASSWORD` 或 `SSH_KEY_PATH` 已配置

### 服务器环境检查
- [ ] 确认服务器已安装 Python 3.9+
- [ ] 确认服务器已安装 Poetry
- [ ] 确认服务器已安装 Node.js 和 npm
- [ ] 确认服务器已安装 nginx
- [ ] 确认服务器已安装 systemd
- [ ] 确认服务器防火墙已开放 `FRONTEND_PORT` 端口

### 本地环境检查
- [ ] 确认本地已安装 sshpass 或 expect（如果使用密码认证）
- [ ] 确认本地可以SSH连接到服务器
- [ ] 确认本地项目代码是最新的

### 部署脚本检查
- [ ] 确认 `deploy.sh` 有执行权限：`chmod +x deploy.sh`
- [ ] 确认 `server_deploy.sh` 有执行权限（会在部署时自动设置）
- [ ] 确认 `nginx.conf.example` 存在

## 🚀 部署步骤

1. **检查配置文件**
   ```bash
   cat .deploy.env
   ```

2. **测试SSH连接**
   ```bash
   ssh -p $SSH_PORT $SERVER_USER@$SERVER_HOST "echo 'SSH连接成功'"
   ```

3. **执行部署**
   ```bash
   ./deploy.sh
   ```

4. **验证部署**
   - 检查服务状态：`ssh $SERVER_USER@$SERVER_HOST "sudo systemctl status stock-scanner.service"`
   - 检查nginx状态：`ssh $SERVER_USER@$SERVER_HOST "sudo systemctl status nginx"`
   - 访问前端：`http://$SERVER_HOST:$FRONTEND_PORT/agent`
   - 访问API文档：`http://$SERVER_HOST:$FRONTEND_PORT/api/docs`

## ⚠️ 常见问题

### 1. 前端构建失败
- 检查npm版本：`npm --version`
- 检查node版本：`node --version`
- 清理并重新安装：`cd frontend && rm -rf node_modules && npm install`

### 2. Poetry安装依赖失败
- 检查Python版本：`python3 --version`
- 检查Poetry版本：`poetry --version`
- 尝试手动安装：`cd $DEPLOY_PATH && poetry install --no-dev`

### 3. Nginx配置错误
- 检查nginx配置：`sudo nginx -t`
- 查看nginx错误日志：`sudo tail -f /var/log/nginx/error.log`
- 检查配置文件：`sudo cat /etc/nginx/conf.d/stock-scanner.conf`

### 4. 后端服务启动失败
- 查看服务日志：`sudo journalctl -u stock-scanner.service -n 50`
- 检查端口占用：`sudo netstat -tlnp | grep $BACKEND_PORT`
- 手动测试启动：`cd $DEPLOY_PATH && poetry run python run_with_backend.py --backend-port $BACKEND_PORT`

### 5. 前端无法访问
- 检查nginx是否运行：`sudo systemctl status nginx`
- 检查dist目录是否存在：`ls -la $DEPLOY_PATH/frontend/dist`
- 检查nginx配置中的路径是否正确
- 检查防火墙是否开放端口

## 📝 部署后验证

1. **前端访问**
   - 访问 `http://$SERVER_HOST:$FRONTEND_PORT/agent` 应该显示前端页面
   - 访问 `http://$SERVER_HOST:$FRONTEND_PORT/` 应该重定向到 `/agent/`

2. **API访问**
   - 访问 `http://$SERVER_HOST:$FRONTEND_PORT/api/docs` 应该显示API文档
   - 测试API端点：`curl http://$SERVER_HOST:$FRONTEND_PORT/api/config/get`

3. **服务状态**
   - 后端服务应该运行：`sudo systemctl is-active stock-scanner.service`
   - Nginx应该运行：`sudo systemctl is-active nginx`

4. **日志检查**
   - 后端日志：`sudo journalctl -u stock-scanner.service -f`
   - Nginx访问日志：`sudo tail -f /var/log/nginx/stock-scanner-access.log`
   - Nginx错误日志：`sudo tail -f /var/log/nginx/stock-scanner-error.log`
