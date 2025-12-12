#!/bin/bash
# 快速配置 Nginx 脚本
# 在服务器上运行此脚本来生成 Nginx 配置文件
# 注意：需要手动将生成的配置文件 include 到主配置中

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 获取部署路径（从环境变量或使用默认值）
DEPLOY_PATH=${DEPLOY_PATH:-/opt/investment_agent}
BACKEND_PORT=${BACKEND_PORT:-8101}
FRONTEND_PATH="/agent"

print_info "开始生成 Nginx 配置文件..."
print_info "部署路径: $DEPLOY_PATH"
print_info "后端端口: $BACKEND_PORT"
print_info "前端访问路径: $FRONTEND_PATH"

# 检查部署路径是否存在
if [ ! -d "$DEPLOY_PATH/frontend/dist" ]; then
    print_error "前端部署路径不存在: $DEPLOY_PATH/frontend/dist"
    print_error "请确认部署路径是否正确，或先运行部署脚本"
    exit 1
fi

# 检查前端文件
if [ ! -f "$DEPLOY_PATH/frontend/dist/index.html" ]; then
    print_error "前端文件不存在: $DEPLOY_PATH/frontend/dist/index.html"
    print_error "请先构建前端应用"
    exit 1
fi

# 检查 Nginx 是否安装
if ! command -v nginx &> /dev/null; then
    print_info "安装 Nginx..."
    if command -v yum &> /dev/null; then
        sudo yum install -y nginx
    elif command -v apt-get &> /dev/null; then
        sudo apt-get update -qq && sudo apt-get install -y nginx
    else
        print_error "无法自动安装 Nginx，请手动安装"
        exit 1
    fi
fi

# 创建 Nginx 配置文件
print_info "生成 Nginx 配置文件..."
NGINX_CONF="/etc/nginx/conf.d/investment-agent.conf"

# 检查配置文件是否已存在
if [ -f "$NGINX_CONF" ]; then
    print_warn "配置文件已存在: $NGINX_CONF"
    print_warn "将备份现有配置..."
    sudo cp "$NGINX_CONF" "${NGINX_CONF}.backup.$(date +%Y%m%d_%H%M%S)"
fi

# 生成配置文件
sudo tee "$NGINX_CONF" > /dev/null <<EOF
server {
    listen 80;
    server_name _;

    # 前端静态文件 - /agent 路径
    location /agent {
        alias $DEPLOY_PATH/frontend/dist;
        index index.html;
        try_files \$uri \$uri/ /agent/index.html;
        
        # 缓存静态资源
        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
    }

    # 后端API代理 - /agent/api/*
    location /agent/api/ {
        rewrite ^/agent/api/(.*)$ /api/\$1 break;
        proxy_pass http://127.0.0.1:${BACKEND_PORT};
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;
        
        # 超时设置
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    # 处理 /agent/api 不带尾部斜杠的情况
    location = /agent/api {
        return 301 /agent/api/;
    }

    # 报告API代理 - /agent/reports
    location /agent/reports {
        rewrite ^/agent/reports(.*)$ /reports\$1 break;
        proxy_pass http://127.0.0.1:${BACKEND_PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # 超时设置
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # 日志API代理 - /agent/logs
    location /agent/logs {
        rewrite ^/agent/logs(.*)$ /logs\$1 break;
        proxy_pass http://127.0.0.1:${BACKEND_PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # 超时设置
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # 运行历史API代理 - /agent/runs
    location /agent/runs {
        rewrite ^/agent/runs(.*)$ /runs\$1 break;
        proxy_pass http://127.0.0.1:${BACKEND_PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # 超时设置
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # WebSocket支持（如果需要） - /agent/ws
    location /agent/ws {
        rewrite ^/agent/ws(.*)$ /ws\$1 break;
        proxy_pass http://127.0.0.1:${BACKEND_PORT};
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        
        # WebSocket超时设置
        proxy_connect_timeout 7d;
        proxy_send_timeout 7d;
        proxy_read_timeout 7d;
    }

    # 日志
    access_log /var/log/nginx/investment-agent-access.log;
    error_log /var/log/nginx/investment-agent-error.log;
}
EOF

print_info "Nginx 配置文件已生成: $NGINX_CONF"

# 测试 Nginx 配置
print_info "测试 Nginx 配置..."
if sudo nginx -t; then
    print_info "✓ Nginx 配置测试通过"
else
    print_error "✗ Nginx 配置测试失败"
    print_error "请检查配置文件: $NGINX_CONF"
    exit 1
fi

# 检查后端服务
print_info "检查后端服务状态..."
if sudo systemctl is-active --quiet stock-scanner.service 2>/dev/null; then
    print_info "✓ 后端服务正在运行"
else
    print_warn "⚠ 后端服务未运行，请启动: sudo systemctl start stock-scanner.service"
fi

# 显示访问信息
SERVER_IP=$(hostname -I | awk '{print $1}' || echo "your-server-ip")
print_info ""
print_info "=========================================="
print_info "配置文件生成完成！"
print_info "=========================================="
print_info "配置文件位置: $NGINX_CONF"
print_info ""
print_info "⚠️  重要提示："
print_info "请确保主配置文件 (/etc/nginx/nginx.conf) 中已包含此配置："
print_info "  include /etc/nginx/conf.d/investment-agent.conf;"
print_info ""
print_info "如果尚未包含，请："
print_info "1. 编辑主配置文件: sudo nano /etc/nginx/nginx.conf"
print_info "2. 在 http {} 块中添加: include /etc/nginx/conf.d/investment-agent.conf;"
print_info "3. 测试配置: sudo nginx -t"
print_info "4. 重载nginx: sudo systemctl reload nginx"
print_info ""
print_info "配置完成后，访问地址："
print_info "  前端: http://$SERVER_IP/agent"
print_info "  API文档: http://$SERVER_IP/agent/api/docs"
print_info "  后端API: http://$SERVER_IP/agent/api"
print_info ""
print_info "访问日志: /var/log/nginx/investment-agent-access.log"
print_info "错误日志: /var/log/nginx/investment-agent-error.log"
