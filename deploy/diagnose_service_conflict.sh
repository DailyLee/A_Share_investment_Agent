#!/bin/bash
# 诊断服务冲突问题

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

print_section "检查端口占用情况"
echo "检查 8001 端口:"
if sudo ss -tlnp | grep :8001; then
    print_info "8001 端口已被占用"
    sudo ss -tlnp | grep :8001 | head -1
else
    print_warn "8001 端口未被占用"
fi

echo ""
echo "检查 8101 端口:"
if sudo ss -tlnp | grep :8101; then
    print_info "8101 端口已被占用"
    sudo ss -tlnp | grep :8101 | head -1
else
    print_warn "8101 端口未被占用"
fi

print_section "检查 Systemd 服务配置"
SERVICE_FILE="/etc/systemd/system/stock-scanner.service"
if [ -f "$SERVICE_FILE" ]; then
    print_info "找到服务文件: $SERVICE_FILE"
    echo ""
    echo "服务配置内容:"
    sudo cat "$SERVICE_FILE"
    echo ""
    
    # 检查工作目录
    WORK_DIR=$(grep "^WorkingDirectory=" "$SERVICE_FILE" | cut -d'=' -f2 || echo "")
    if [ -n "$WORK_DIR" ]; then
        print_info "工作目录: $WORK_DIR"
        if [ -d "$WORK_DIR" ]; then
            print_info "工作目录存在"
        else
            print_error "工作目录不存在: $WORK_DIR"
        fi
    fi
    
    # 检查端口配置
    PORT=$(grep -oP '--backend-port \K[0-9]+' "$SERVICE_FILE" || echo "")
    if [ -n "$PORT" ]; then
        print_info "配置的端口: $PORT"
    fi
else
    print_warn "服务文件不存在: $SERVICE_FILE"
fi

# 检查是否有其他相关服务
print_section "检查其他相关服务"
echo "查找所有包含 'stock' 或 'scanner' 的服务:"
systemctl list-units --type=service | grep -iE "stock|scanner" || print_warn "未找到相关服务"

print_section "检查服务状态"
if [ -f "$SERVICE_FILE" ]; then
    if sudo systemctl is-active --quiet stock-scanner.service 2>/dev/null; then
        print_info "stock-scanner.service 正在运行"
        echo ""
        echo "服务状态:"
        sudo systemctl status stock-scanner.service --no-pager -l | head -15
    else
        print_warn "stock-scanner.service 未运行"
    fi
fi

print_section "检查服务日志（最近20行）"
if [ -f "$SERVICE_FILE" ]; then
    if sudo systemctl is-active --quiet stock-scanner.service 2>/dev/null; then
        echo "服务日志:"
        sudo journalctl -u stock-scanner.service -n 20 --no-pager || print_warn "无法获取服务日志"
    fi
fi

print_section "检查进程"
echo "查找 Python 进程:"
ps aux | grep -E "python.*run_with_backend|uvicorn" | grep -v grep || print_warn "未找到相关进程"

print_section "检查文件锁和资源"
# 检查是否有 Python 锁文件
if [ -n "$WORK_DIR" ] && [ -d "$WORK_DIR" ]; then
    echo "检查工作目录中的锁文件:"
    find "$WORK_DIR" -name "*.lock" -o -name "*.pid" 2>/dev/null | head -10 || print_info "未找到锁文件"
fi

print_section "检查环境变量冲突"
echo "检查可能冲突的环境变量:"
env | grep -iE "PORT|BACKEND|API|PATH" | sort

print_section "建议的解决方案"
echo "1. 确保两个服务使用不同的端口（8001 和 8101）"
echo "2. 确保两个服务使用不同的工作目录"
echo "3. 确保两个服务使用不同的 systemd 服务名称"
echo "4. 检查是否有共享的全局状态或单例对象"
echo "5. 检查日志文件路径是否冲突"
echo ""
echo "如果问题仍然存在，请检查："
echo "  - 两个服务是否共享同一个 FastAPI app 实例"
echo "  - 两个服务是否共享同一个 api_state 实例"
echo "  - 是否有文件锁或数据库连接冲突"

