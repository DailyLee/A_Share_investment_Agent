#!/bin/bash

# 服务器端部署脚本
# 此脚本在远程服务器上执行，用于设置和启动服务

set -e  # 遇到错误立即退出

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

# 获取脚本所在目录（部署路径）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

print_info "开始服务器端部署..."

# 检查配置文件（在部署路径根目录）
if [ ! -f ".deploy.env" ]; then
    print_error "配置文件 .deploy.env 不存在！"
    print_error "请确保 .deploy.env 文件已上传到部署路径: $SCRIPT_DIR"
    exit 1
fi

# 加载配置
while IFS='=' read -r key value; do
    [[ "$key" =~ ^#.*$ ]] && continue
    [[ -z "$key" ]] && continue
    key=$(echo "$key" | xargs)
    value=$(echo "$value" | xargs)
    value=$(echo "$value" | sed "s/^['\"]//; s/['\"]$//")
    export "$key=$value"
done < .deploy.env

# 设置默认值（注意：DEPLOY_PATH应该从.deploy.env读取，这里只是备用默认值）
FRONTEND_PORT=${FRONTEND_PORT:-80}
BACKEND_PORT=${BACKEND_PORT:-8001}
# 如果DEPLOY_PATH未设置，使用当前脚本所在目录
DEPLOY_PATH=${DEPLOY_PATH:-$(pwd)}

print_info "前端端口: $FRONTEND_PORT"
print_info "后端端口: $BACKEND_PORT"
print_info "部署路径: $DEPLOY_PATH"

# 1. 安装Python依赖
print_info "安装Python依赖..."
# 确保在部署路径下
cd "$SCRIPT_DIR"

# 检查poetry是否安装（使用多种方法）
POETRY_CMD=""
if command -v poetry &> /dev/null; then
    POETRY_CMD="poetry"
elif [ -f "$HOME/.local/bin/poetry" ]; then
    POETRY_CMD="$HOME/.local/bin/poetry"
elif [ -f "/usr/local/bin/poetry" ]; then
    POETRY_CMD="/usr/local/bin/poetry"
elif which poetry &> /dev/null; then
    POETRY_CMD=$(which poetry)
else
    # 尝试直接运行poetry --version来检测
    if poetry --version &> /dev/null; then
        POETRY_CMD="poetry"
    fi
fi

if [ -z "$POETRY_CMD" ]; then
    print_error "poetry未安装或不在PATH中！此项目必须使用poetry管理依赖"
    print_info "检测方法："
    print_info "  1. 检查 command -v poetry"
    print_info "  2. 检查 ~/.local/bin/poetry"
    print_info "  3. 检查 /usr/local/bin/poetry"
    print_info "  4. 检查 which poetry"
    print_info "安装poetry的方法："
    print_info "  curl -sSL https://install.python-poetry.org | python3 -"
    print_info "  或者: pip install poetry"
    print_info "  安装后需要将poetry添加到PATH: export PATH=\"\$HOME/.local/bin:\$PATH\""
    exit 1
fi

# 验证poetry是否可用
if ! $POETRY_CMD --version &> /dev/null; then
    print_error "poetry命令无法执行，请检查安装"
    exit 1
fi

POETRY_VERSION=$($POETRY_CMD --version 2>&1)
print_info "检测到poetry: $POETRY_VERSION"

# 提取Poetry主版本号（提前提取，供后续使用）
POETRY_MAJOR_VERSION=$(echo "$POETRY_VERSION" | grep -oE 'version [0-9]+' | grep -oE '[0-9]+' | head -1)

# 检查pyproject.toml是否存在
if [ ! -f "pyproject.toml" ]; then
    print_error "pyproject.toml文件不存在！"
    print_error "请确保项目文件已正确上传到部署路径: $SCRIPT_DIR"
    exit 1
fi

# 检查并更新poetry.lock文件
print_info "检查poetry.lock文件..."
if [ ! -f "poetry.lock" ]; then
    print_warn "poetry.lock文件不存在，正在生成..."
    # 设置环境变量增加超时时间
    export PIP_DEFAULT_TIMEOUT=300
    export PIP_CONNECT_TIMEOUT=60
    set +e
    # Poetry 2.0+ 不需要 --no-update，直接使用 lock
    # Poetry 1.x 需要使用 --no-update
    if [ -n "$POETRY_MAJOR_VERSION" ] && [ "$POETRY_MAJOR_VERSION" -ge 2 ]; then
        print_info "使用Poetry 2.0+语法: poetry lock"
        $POETRY_CMD lock 2>&1
        LOCK_GEN_EXIT=$?
    else
        print_info "使用Poetry 1.x语法: poetry lock --no-update"
        $POETRY_CMD lock --no-update 2>&1
        LOCK_GEN_EXIT=$?
        if [ $LOCK_GEN_EXIT -ne 0 ]; then
            print_warn "使用 --no-update 失败，尝试完整更新..."
            $POETRY_CMD lock 2>&1
            LOCK_GEN_EXIT=$?
        fi
    fi
    set -e
    if [ $LOCK_GEN_EXIT -ne 0 ]; then
        print_error "生成poetry.lock失败！"
        print_error "请检查网络连接和pyproject.toml配置"
        exit 1
    fi
    print_info "poetry.lock文件已生成"
else
    # 检查poetry.lock文件是否存在且有效
    print_info "检查poetry.lock文件..."
    # 简单检查文件是否存在，实际的同步检查将在安装时进行
    if [ -f "poetry.lock" ]; then
        print_info "poetry.lock文件存在，将在安装时检查同步状态"
    fi
fi

# 根据Poetry版本选择正确的安装选项
# Poetry 2.0+ 移除了 --no-dev，改用 --only main 或 --without dev
# POETRY_MAJOR_VERSION 已在前面提取
POETRY_INSTALL_OPTION=""
if [ -n "$POETRY_MAJOR_VERSION" ] && [ "$POETRY_MAJOR_VERSION" -ge 2 ]; then
    # Poetry 2.0+ 使用 --only main
    POETRY_INSTALL_OPTION="--only main"
    print_info "使用Poetry 2.0+语法: poetry install $POETRY_INSTALL_OPTION"
else
    # Poetry 1.x 使用 --no-dev，如果版本检测失败也尝试 --no-dev
    POETRY_INSTALL_OPTION="--no-dev"
    print_info "使用Poetry 1.x语法: poetry install $POETRY_INSTALL_OPTION"
fi

# 配置Poetry使用国内镜像源（如果pyproject.toml中没有配置）
if ! grep -q "tool.poetry.source" pyproject.toml 2>/dev/null; then
    print_info "配置Poetry使用国内镜像源..."
    # 添加清华镜像源
    $POETRY_CMD source add --priority=supplemental tsinghua https://pypi.tuna.tsinghua.edu.cn/simple 2>/dev/null || true
fi

print_info "使用poetry安装依赖（带重试机制）..."
MAX_RETRIES=3
RETRY_COUNT=0
INSTALL_SUCCESS=false

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if [ $RETRY_COUNT -gt 0 ]; then
        print_warn "第 $((RETRY_COUNT + 1)) 次尝试安装依赖..."
        sleep 5  # 等待5秒后重试
    fi
    
    # 设置环境变量增加超时时间
    export PIP_DEFAULT_TIMEOUT=300
    export PIP_CONNECT_TIMEOUT=60
    
    print_info "执行: $POETRY_CMD install $POETRY_INSTALL_OPTION"
    # 临时禁用 set -e，以便捕获错误信息
    set +e
    INSTALL_OUTPUT=$($POETRY_CMD install $POETRY_INSTALL_OPTION 2>&1)
    INSTALL_EXIT=$?
    set -e  # 重新启用 set -e
    
    if [ $INSTALL_EXIT -eq 0 ]; then
        INSTALL_SUCCESS=true
        print_info "依赖安装成功！"
        break
    else
        # 显示错误信息
        print_error "安装失败（退出码: $INSTALL_EXIT），错误信息："
        echo "$INSTALL_OUTPUT" | tail -30  # 显示最后30行错误信息
        
        # 检查是否是lock文件不同步的问题
        if echo "$INSTALL_OUTPUT" | grep -qi "poetry lock"; then
            print_warn "检测到poetry.lock文件不同步，正在更新..."
            export PIP_DEFAULT_TIMEOUT=300
            export PIP_CONNECT_TIMEOUT=60
            set +e
            # Poetry 2.0+ 不需要 --no-update，直接使用 lock
            # Poetry 1.x 需要使用 --no-update
            if [ -n "$POETRY_MAJOR_VERSION" ] && [ "$POETRY_MAJOR_VERSION" -ge 2 ]; then
                print_info "使用Poetry 2.0+语法: poetry lock"
                $POETRY_CMD lock 2>&1
                LOCK_UPDATE_EXIT=$?
            else
                print_info "使用Poetry 1.x语法: poetry lock --no-update"
                $POETRY_CMD lock --no-update 2>&1
                LOCK_UPDATE_EXIT=$?
                if [ $LOCK_UPDATE_EXIT -ne 0 ]; then
                    print_warn "使用 --no-update 失败，尝试完整更新..."
                    $POETRY_CMD lock 2>&1
                    LOCK_UPDATE_EXIT=$?
                fi
            fi
            set -e
            if [ $LOCK_UPDATE_EXIT -ne 0 ]; then
                print_error "更新poetry.lock失败！"
                print_error "请手动运行: cd $SCRIPT_DIR && $POETRY_CMD lock"
                exit 1
            fi
            print_info "poetry.lock已更新，将重新尝试安装..."
            # 重置重试计数，因为这是修复问题，不算重试
            RETRY_COUNT=0
            continue
        else
            RETRY_COUNT=$((RETRY_COUNT + 1))
            if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
                print_warn "安装失败，将在5秒后重试... (尝试 $RETRY_COUNT/$MAX_RETRIES)"
            fi
        fi
    fi
done

if [ "$INSTALL_SUCCESS" = false ]; then
    # 如果 --only main 失败，尝试 --without dev（Poetry 2.0+ 的另一种方式）
    if [ "$POETRY_INSTALL_OPTION" = "--only main" ]; then
        print_warn "使用 --only main 失败，尝试 --without dev..."
        RETRY_COUNT=0
        while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
            if [ $RETRY_COUNT -gt 0 ]; then
                print_warn "第 $((RETRY_COUNT + 1)) 次尝试安装依赖..."
                sleep 5
            fi
            
            set +e
            INSTALL_OUTPUT2=$($POETRY_CMD install --without dev 2>&1)
            INSTALL_EXIT2=$?
            set -e
            if [ $INSTALL_EXIT2 -eq 0 ]; then
                INSTALL_SUCCESS=true
                print_info "依赖安装成功！"
                break
            else
                print_error "安装失败（退出码: $INSTALL_EXIT2），错误信息："
                echo "$INSTALL_OUTPUT2" | tail -30
                RETRY_COUNT=$((RETRY_COUNT + 1))
            fi
        done
    fi
    
    if [ "$INSTALL_SUCCESS" = false ]; then
        print_error "poetry install 失败！已重试 $MAX_RETRIES 次"
        print_error "可能的原因："
        print_error "1. 网络连接问题（超时）"
        print_error "2. pyproject.toml文件配置错误"
        print_error "3. 依赖包版本冲突"
        print_info "建议："
        print_info "1. 检查网络连接"
        print_info "2. 手动运行: cd $SCRIPT_DIR && $POETRY_CMD install $POETRY_INSTALL_OPTION"
        print_info "3. 检查pyproject.toml中的镜像源配置"
        exit 1
    fi
fi

print_info "Python依赖安装完成"

# 2. 构建前端
print_info "构建前端..."
# 确保在部署路径下
cd "$SCRIPT_DIR"
if [ -d "frontend" ]; then
    cd frontend
    if command -v npm &> /dev/null; then
        print_info "安装前端依赖..."
        # 清理旧的node_modules和package-lock.json以确保依赖更新
        if [ -d "node_modules" ]; then
            print_info "清理旧的node_modules..."
            rm -rf node_modules
        fi
        if [ -f "package-lock.json" ]; then
            rm -f package-lock.json
        fi
        npm install --production=false
        print_info "构建前端应用..."
        npm run build
        if [ ! -d "dist" ]; then
            print_error "前端构建失败，dist目录不存在"
            exit 1
        fi
        print_info "前端构建完成"
        cd ..
    else
        print_error "npm未安装，无法构建前端"
        exit 1
    fi
else
    print_warn "frontend目录不存在，跳过前端构建"
fi

# 3. Nginx配置提示
print_info "=== Nginx配置提示 ==="
print_info "请手动在服务器上配置nginx，参考配置示例："
if [ -f "$SCRIPT_DIR/deploy/nginx.conf.example" ]; then
    print_info "配置文件示例位置: $SCRIPT_DIR/deploy/nginx.conf.example"
elif [ -f "$SCRIPT_DIR/nginx.conf.example" ]; then
    print_info "配置文件示例位置: $SCRIPT_DIR/nginx.conf.example"
fi
print_info ""
print_info "配置要点："
print_info "1. 前端静态文件路径: $DEPLOY_PATH/frontend/dist"
print_info "2. 前端访问路径: /agent"
print_info "3. 后端API代理: http://127.0.0.1:$BACKEND_PORT"
print_info "4. 前端端口: $FRONTEND_PORT"
print_info ""
print_info "配置完成后，请运行以下命令测试并重载nginx："
print_info "  sudo nginx -t"
print_info "  sudo systemctl reload nginx"
print_info ""

# 4. 创建/更新systemd服务文件
print_info "配置systemd服务..."
SERVICE_FILE="/etc/systemd/system/stock-scanner.service"

# 检查是否需要更新服务文件（如果端口配置改变）
NEED_UPDATE=false
if [ -f "$SERVICE_FILE" ]; then
    # 检查当前服务文件中的端口是否与配置一致
    CURRENT_PORT=$(grep -oP '--backend-port \K[0-9]+' "$SERVICE_FILE" || echo "")
    if [ "$CURRENT_PORT" != "$BACKEND_PORT" ]; then
        print_info "检测到端口配置变化 ($CURRENT_PORT -> $BACKEND_PORT)，需要更新服务文件"
        NEED_UPDATE=true
    fi
else
    NEED_UPDATE=true
fi

if [ "$NEED_UPDATE" = true ]; then
    # 确定poetry路径（如果之前没有设置，重新检测）
    if [ -z "$POETRY_CMD" ]; then
        if command -v poetry &> /dev/null; then
            POETRY_CMD="poetry"
        elif [ -f "$HOME/.local/bin/poetry" ]; then
            POETRY_CMD="$HOME/.local/bin/poetry"
        elif [ -f "/usr/local/bin/poetry" ]; then
            POETRY_CMD="/usr/local/bin/poetry"
        else
            POETRY_CMD="poetry"
        fi
    fi
    
    # 确定Poetry虚拟环境路径
    # Poetry默认将虚拟环境放在 ~/.cache/pypoetry/virtualenvs/ 或项目目录下
    # 使用 poetry env info 获取实际路径，如果失败则使用默认路径
    VENV_PATH=""
    if [ -n "$POETRY_CMD" ] && $POETRY_CMD --version &> /dev/null; then
        POETRY_ENV_INFO=$(cd "$DEPLOY_PATH" && $POETRY_CMD env info --path 2>/dev/null || echo "")
        if [ -n "$POETRY_ENV_INFO" ] && [ -d "$POETRY_ENV_INFO" ]; then
            VENV_PATH="$POETRY_ENV_INFO/bin"
        fi
    fi
    
    # 如果找不到Poetry虚拟环境，尝试常见路径
    if [ -z "$VENV_PATH" ]; then
        if [ -d "$DEPLOY_PATH/.venv/bin" ]; then
            VENV_PATH="$DEPLOY_PATH/.venv/bin"
        elif [ -d "$HOME/.cache/pypoetry/virtualenvs" ]; then
            # Poetry可能使用全局虚拟环境
            VENV_PATH=""
        fi
    fi
    
    # 构建PATH环境变量
    if [ -n "$VENV_PATH" ]; then
        ENV_PATH="$VENV_PATH:/usr/local/bin:/usr/bin:/bin"
    else
        # 如果找不到虚拟环境，依赖poetry run来管理环境
        ENV_PATH="/usr/local/bin:/usr/bin:/bin"
    fi
    
    cat > /tmp/stock-scanner.service << EOF
[Unit]
Description=Stock Scanner Backend Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$DEPLOY_PATH
Environment="PATH=$ENV_PATH"
ExecStart=$POETRY_CMD run python run_with_backend.py --backend-port $BACKEND_PORT
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    
    sudo cp /tmp/stock-scanner.service "$SERVICE_FILE"
    sudo systemctl daemon-reload
    print_info "Systemd服务文件已更新: $SERVICE_FILE"
else
    print_info "Systemd服务文件已存在且配置正确，跳过更新"
fi

# 5. 启动/重启服务
print_info "启动后端服务..."
sudo systemctl enable stock-scanner.service
sudo systemctl restart stock-scanner.service

# 等待服务启动
sleep 3

# 检查服务状态
if sudo systemctl is-active --quiet stock-scanner.service; then
    print_info "后端服务已成功启动"
else
    print_error "后端服务启动失败"
    sudo systemctl status stock-scanner.service
    exit 1
fi

print_info "部署完成！"
print_info ""
print_info "=== 重要提示 ==="
print_info "请手动配置nginx以访问前端应用"
print_info "前端静态文件路径: $DEPLOY_PATH/frontend/dist"
print_info "后端API地址: http://127.0.0.1:$BACKEND_PORT (仅本地访问)"
print_info ""
print_info "配置nginx后，访问地址："
print_info "  前端: http://$(hostname -I | awk '{print $1}'):$FRONTEND_PORT/agent"
print_info "  API文档: http://$(hostname -I | awk '{print $1}'):$FRONTEND_PORT/api/docs"
print_info ""
print_info "查看服务状态: sudo systemctl status stock-scanner.service"
print_info "查看服务日志: sudo journalctl -u stock-scanner.service -f"
