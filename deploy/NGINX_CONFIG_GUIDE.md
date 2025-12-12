# Nginx 配置指南

本文档说明如何在服务器上配置 nginx，使前后端正常运行。

## 📋 配置前准备

根据你的 `.deploy.env` 配置：
- **部署路径**: `/opt/investment_agent`
- **后端端口**: `8101`
- **前端访问路径**: `/agent`
- **前端端口**: `80` (HTTP默认端口)

## 🔧 配置步骤

### 1. 在服务器上创建 nginx 配置文件

```bash
# SSH登录到服务器
ssh root@121.43.251.23

# 创建nginx配置文件
sudo nano /etc/nginx/conf.d/investment-agent.conf
```

### 2. 复制以下配置内容

根据你的实际配置修改以下内容：

```nginx
server {
    listen 80;
    server_name 121.43.251.23;  # 修改为你的服务器IP或域名

    # 前端静态文件 - 部署在 /agent 路径下
    location /agent {
        alias /opt/investment_agent/frontend/dist;
        index index.html;
        try_files $uri $uri/ /agent/index.html;
        
        # 缓存静态资源
        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
    }
    
    # 重定向根路径到 /agent
    location = / {
        return 301 /agent/;
    }

    # 后端API代理 - /api/*
    location /api {
        proxy_pass http://127.0.0.1:8101;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        
        # 超时设置
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # 报告API代理
    location /reports {
        proxy_pass http://127.0.0.1:8101;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # 超时设置
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # 日志API代理
    location /logs {
        proxy_pass http://127.0.0.1:8101;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # 超时设置
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # 运行历史API代理
    location /runs {
        proxy_pass http://127.0.0.1:8101;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # 超时设置
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # WebSocket支持（如果需要）
    location /ws {
        proxy_pass http://127.0.0.1:8101;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # 日志
    access_log /var/log/nginx/investment-agent-access.log;
    error_log /var/log/nginx/investment-agent-error.log;
}
```

### 3. 重要配置说明

#### 需要修改的地方：

1. **server_name**: 
   - 如果使用IP访问：`server_name 121.43.251.23;`
   - 如果使用域名：`server_name your-domain.com;`
   - 如果服务器上已有其他服务使用80端口，可以设置具体的server_name来区分

2. **前端路径** (`alias`):
   - 确保路径正确：`/opt/investment_agent/frontend/dist`
   - 如果部署路径不同，请相应修改

3. **后端端口** (`proxy_pass`):
   - 当前配置为：`http://127.0.0.1:8101`
   - 如果后端端口不同，请修改所有 `proxy_pass` 中的端口号

### 4. 测试配置

```bash
# 测试nginx配置语法
sudo nginx -t

# 如果测试通过，会显示：
# nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
# nginx: configuration file /etc/nginx/nginx.conf test is successful
```

### 5. 重载nginx

```bash
# 重载nginx配置（不中断服务）
sudo systemctl reload nginx

# 或者重启nginx
sudo systemctl restart nginx
```

### 6. 验证配置

#### 检查nginx状态
```bash
sudo systemctl status nginx
```

#### 检查端口监听
```bash
# 检查80端口是否被nginx监听
sudo ss -tlnp | grep :80
# 或
sudo netstat -tlnp | grep :80
```

#### 检查前端文件
```bash
# 确认前端dist目录存在
ls -la /opt/investment_agent/frontend/dist

# 确认index.html存在
ls -la /opt/investment_agent/frontend/dist/index.html
```

#### 检查后端服务
```bash
# 确认后端服务正在运行
sudo systemctl status stock-scanner.service

# 检查后端端口是否监听
sudo ss -tlnp | grep :8101
```

### 7. 测试访问

在浏览器中访问：
- **前端**: `http://121.43.251.23/agent`
- **API文档**: `http://121.43.251.23/api/docs`
- **API测试**: `http://121.43.251.23/api/config/get`

## 🔍 故障排查

### 问题1: 无法访问前端页面

**检查步骤：**
```bash
# 1. 检查nginx是否运行
sudo systemctl status nginx

# 2. 检查nginx错误日志
sudo tail -f /var/log/nginx/investment-agent-error.log

# 3. 检查前端文件是否存在
ls -la /opt/investment_agent/frontend/dist

# 4. 检查文件权限
sudo chown -R nginx:nginx /opt/investment_agent/frontend/dist
# 或
sudo chown -R www-data:www-data /opt/investment_agent/frontend/dist
```

### 问题2: API请求失败

**检查步骤：**
```bash
# 1. 检查后端服务是否运行
sudo systemctl status stock-scanner.service

# 2. 检查后端日志
sudo journalctl -u stock-scanner.service -n 50

# 3. 测试后端是否响应
curl http://127.0.0.1:8101/api/config/get

# 4. 检查nginx访问日志
sudo tail -f /var/log/nginx/investment-agent-access.log
```

### 问题3: 403 Forbidden 错误

**可能原因：**
- 文件权限问题
- 目录索引被禁用

**解决方法：**
```bash
# 修改文件权限
sudo chmod -R 755 /opt/investment_agent/frontend/dist
sudo chown -R nginx:nginx /opt/investment_agent/frontend/dist
```

### 问题4: 404 Not Found 错误

**可能原因：**
- 前端文件路径不正确
- 前端未正确构建

**解决方法：**
```bash
# 检查前端是否已构建
ls -la /opt/investment_agent/frontend/dist

# 如果不存在，需要重新构建前端
cd /opt/investment_agent/frontend
npm install
npm run build
```

### 问题5: 502 Bad Gateway 错误

**可能原因：**
- 后端服务未运行
- 后端端口配置错误

**解决方法：**
```bash
# 检查后端服务
sudo systemctl status stock-scanner.service

# 启动后端服务
sudo systemctl start stock-scanner.service

# 检查后端端口
sudo ss -tlnp | grep :8101
```

## 🔐 防火墙配置

如果无法访问，请检查防火墙：

```bash
# CentOS/RHEL (firewalld)
sudo firewall-cmd --permanent --add-port=80/tcp
sudo firewall-cmd --reload

# Ubuntu/Debian (ufw)
sudo ufw allow 80/tcp

# 或使用iptables
sudo iptables -I INPUT -p tcp --dport 80 -j ACCEPT
```

## 📝 注意事项

1. **如果服务器上已有其他服务使用80端口**：
   - 可以使用不同的 `server_name` 来区分
   - 或者使用不同的端口（如8100），然后通过 `http://ip:8100/agent` 访问

2. **文件权限**：
   - nginx 需要读取前端静态文件的权限
   - 确保 `/opt/investment_agent/frontend/dist` 目录对 nginx 用户可读

3. **SELinux**（如果启用）：
   ```bash
   # 允许nginx访问文件
   sudo setsebool -P httpd_read_user_content 1
   ```

4. **日志位置**：
   - 访问日志：`/var/log/nginx/investment-agent-access.log`
   - 错误日志：`/var/log/nginx/investment-agent-error.log`

## ✅ 配置完成检查清单

- [ ] nginx配置文件已创建并修改正确
- [ ] nginx配置测试通过 (`sudo nginx -t`)
- [ ] nginx已重载或重启
- [ ] 前端dist目录存在且权限正确
- [ ] 后端服务正在运行
- [ ] 防火墙已开放80端口
- [ ] 可以访问 `http://ip/agent`
- [ ] 可以访问 `http://ip/api/docs`
