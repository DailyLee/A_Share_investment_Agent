#!/bin/bash
# 诊断 502 错误的脚本
# 在服务器上运行此脚本来检查后端服务和 Nginx 配置

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

print_section() {
    echo -e "\n${BLUE}=== $1 ===${NC}"
}

# 获取配置
DEPLOY_PATH=${DEPLOY_PATH:-/opt/investment_agent}
BACKEND_PORT=${BACKEND_PORT:-8101}

print_section "检查后端服务状态"
if sudo systemctl is-active --quiet stock-scanner.service 2>/dev/null; then
    print_info "✓ 后端服务正在运行"
    sudo systemctl status stock-scanner.service --no-pager -l | head -20
else
    print_error "✗ 后端服务未运行"
    print_info "尝试启动服务..."
    sudo systemctl start stock-scanner.service
    sleep 2
    if sudo systemctl is-active --quiet stock-scanner.service 2>/dev/null; then
        print_info "✓ 服务已启动"
    else
        print_error "✗ 服务启动失败"
        print_info "查看服务日志:"
        sudo journalctl -u stock-scanner.service -n 50 --no-pager
    fi
fi

print_section "检查后端端口监听"
if sudo ss -tlnp | grep -q ":${BACKEND_PORT}"; then
    print_info "✓ 端口 ${BACKEND_PORT} 正在监听"
    sudo ss -tlnp | grep ":${BACKEND_PORT}"
else
    print_error "✗ 端口 ${BACKEND_PORT} 未监听"
    print_warn "可能的原因："
    print_warn "  1. 后端服务未启动"
    print_warn "  2. 后端服务配置的端口不是 ${BACKEND_PORT}"
    print_warn "  3. 服务启动失败"
fi

print_section "测试后端 API 连接"
print_info "测试本地连接: http://127.0.0.1:${BACKEND_PORT}/api"
if curl -s -o /dev/null -w "%{http_code}" --max-time 5 "http://127.0.0.1:${BACKEND_PORT}/api" | grep -q "200\|404"; then
    print_info "✓ 后端 API 可以访问"
    print_info "测试 /api/analysis/start 端点:"
    curl -s "http://127.0.0.1:${BACKEND_PORT}/api/analysis/start" -X POST \
        -H "Content-Type: application/json" \
        -d '{"ticker":"test"}' | head -20 || print_warn "端点可能返回错误（这是正常的，因为测试数据）"
else
    print_error "✗ 无法连接到后端 API"
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "http://127.0.0.1:${BACKEND_PORT}/api" || echo "000")
    print_error "HTTP 状态码: $HTTP_CODE"
fi

print_section "检查 Nginx 配置"
NGINX_CONF="/etc/nginx/conf.d/investment-agent.conf"
if [ -f "$NGINX_CONF" ]; then
    print_info "✓ 找到配置文件: $NGINX_CONF"
    print_info "检查 /agent/api location 配置:"
    grep -A 10 "location /agent/api" "$NGINX_CONF" || print_error "未找到 /agent/api location"
    
    print_info "检查后端端口配置:"
    if grep -q "proxy_pass.*${BACKEND_PORT}" "$NGINX_CONF"; then
        print_info "✓ 配置文件中使用了端口 ${BACKEND_PORT}"
    else
        print_warn "⚠ 配置文件中可能使用了不同的端口"
        grep "proxy_pass" "$NGINX_CONF" | head -5
    fi
else
    print_error "✗ 未找到 Nginx 配置文件: $NGINX_CONF"
    print_info "请先运行 setup_nginx.sh 生成配置"
fi

print_section "测试 Nginx 配置"
if sudo nginx -t 2>&1; then
    print_info "✓ Nginx 配置语法正确"
else
    print_error "✗ Nginx 配置有错误"
fi

print_section "检查 Nginx 是否包含配置文件"
if grep -q "investment-agent.conf" /etc/nginx/nginx.conf 2>/dev/null || \
   [ -f "/etc/nginx/conf.d/investment-agent.conf" ]; then
    print_info "✓ Nginx 配置文件存在"
else
    print_warn "⚠ 请确保主配置文件包含: include /etc/nginx/conf.d/investment-agent.conf;"
fi

print_section "测试通过 Nginx 访问"
print_info "测试: http://127.0.0.1/agent/api"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "http://127.0.0.1/agent/api" || echo "000")
if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "404" ]; then
    print_info "✓ 通过 Nginx 可以访问 API (HTTP $HTTP_CODE)"
elif [ "$HTTP_CODE" = "502" ]; then
    print_error "✗ 502 Bad Gateway - Nginx 无法连接到后端"
    print_warn "可能的原因："
    print_warn "  1. 后端服务未运行"
    print_warn "  2. 后端端口配置不匹配"
    print_warn "  3. 防火墙阻止了连接"
else
    print_warn "HTTP 状态码: $HTTP_CODE"
fi

print_section "检查服务日志"
print_info "最近的后端服务日志:"
sudo journalctl -u stock-scanner.service -n 20 --no-pager | tail -10 || print_warn "无法获取服务日志"

print_section "检查 Nginx 错误日志"
if [ -f "/var/log/nginx/investment-agent-error.log" ]; then
    print_info "最近的 Nginx 错误:"
    sudo tail -20 /var/log/nginx/investment-agent-error.log
else
    print_warn "未找到 Nginx 错误日志"
fi

print_section "诊断总结"
echo ""
print_info "如果后端服务未运行，请执行:"
print_info "  sudo systemctl start stock-scanner.service"
print_info "  sudo systemctl status stock-scanner.service"
echo ""
print_info "如果端口不匹配，请检查:"
print_info "  1. .deploy.env 中的 BACKEND_PORT"
print_info "  2. 服务文件中的端口配置: sudo cat /etc/systemd/system/stock-scanner.service"
echo ""
print_info "查看完整服务日志:"
print_info "  sudo journalctl -u stock-scanner.service -f"
