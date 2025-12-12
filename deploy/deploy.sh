#!/bin/bash

# 自动化部署脚本 - 部署到阿里云ECS
# 系统: Alibaba Cloud Linux 3.2104 LTS 64位
# 使用方法: ./deploy.sh

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 获取项目根目录（deploy目录的父目录）
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 检查配置文件是否存在（在项目根目录）
if [ ! -f "$PROJECT_ROOT/.deploy.env" ]; then
    print_error "配置文件 .deploy.env 不存在！"
    print_info "请复制 deploy/.deploy.env.example 为项目根目录的 .deploy.env 并填写配置信息"
    print_info "命令: cp $DEPLOY_DIR/.deploy.env.example $PROJECT_ROOT/.deploy.env"
    exit 1
fi

# 加载配置（安全地读取，避免特殊字符问题）
while IFS='=' read -r key value; do
    # 跳过注释和空行
    [[ "$key" =~ ^#.*$ ]] && continue
    [[ -z "$key" ]] && continue
    
    # 移除key和value的前后空格
    key=$(echo "$key" | xargs)
    value=$(echo "$value" | xargs)
    
    # 移除value的引号（如果有）
    value=$(echo "$value" | sed "s/^['\"]//; s/['\"]$//")
    
    # 导出变量
    export "$key=$value"
done < "$PROJECT_ROOT/.deploy.env"

# 检查必要的配置项
if [ -z "$SERVER_HOST" ] || [ -z "$SERVER_USER" ] || [ -z "$DEPLOY_PATH" ]; then
    print_error "配置文件 .deploy.env 中缺少必要的配置项！"
    exit 1
fi

# 确定认证方式
USE_PASSWORD=false
USE_EXPECT=false
if [ -n "$SERVER_PASSWORD" ]; then
    USE_PASSWORD=true
    # 检查是否安装了sshpass或expect
    if command -v sshpass &> /dev/null; then
        USE_EXPECT=false
    elif command -v expect &> /dev/null; then
        USE_EXPECT=true
        print_info "使用 expect 进行密码认证"
    else
        print_error "使用密码认证需要安装 sshpass 或 expect 工具"
        print_info "macOS安装expect: brew install expect"
        print_info "macOS安装sshpass: brew install hudochenkov/sshpass/sshpass"
        print_info "Linux安装: sudo apt-get install expect sshpass 或 sudo yum install expect sshpass"
        exit 1
    fi
elif [ -n "$SSH_KEY_PATH" ] && [ -f "$SSH_KEY_PATH" ]; then
    USE_PASSWORD=false
    SSH_OPTIONS="-i $SSH_KEY_PATH"
else
    # 尝试使用默认SSH密钥
    USE_PASSWORD=false
    SSH_OPTIONS=""
fi

# 设置SSH端口
SSH_PORT=${SSH_PORT:-22}
# 确保SSH_OPTIONS没有前导空格
if [ -n "$SSH_OPTIONS" ]; then
    SSH_OPTIONS="$SSH_OPTIONS -p $SSH_PORT -o StrictHostKeyChecking=no"
else
    SSH_OPTIONS="-p $SSH_PORT -o StrictHostKeyChecking=no"
fi
# SCP使用-P（大写）指定端口，SSH使用-p（小写）
SCP_OPTIONS="$SSH_OPTIONS"
SCP_OPTIONS=$(echo "$SCP_OPTIONS" | sed "s/-p $SSH_PORT/-P $SSH_PORT/")

print_info "开始部署到服务器: $SERVER_HOST"
print_info "部署路径: $DEPLOY_PATH"
print_info "认证方式: $([ "$USE_PASSWORD" = true ] && echo "密码认证" || echo "密钥认证")"

# 构建SSH命令前缀
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# 项目根目录
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
if [ "$USE_PASSWORD" = true ]; then
    if [ "$USE_EXPECT" = true ]; then
        # 使用expect进行密码认证
        # 优先使用expect脚本（如果存在），否则直接使用expect命令
        if [ -f "$SCRIPT_DIR/ssh_with_password.sh" ]; then
            SSH_CMD="$SCRIPT_DIR/ssh_with_password.sh '$SERVER_PASSWORD' ssh $SSH_OPTIONS"
            SCP_CMD="$SCRIPT_DIR/ssh_with_password.sh '$SERVER_PASSWORD' scp $SCP_OPTIONS"
            RSYNC_CMD="rsync"
        else
            # 直接使用expect命令（expect已安装）
            print_info "使用expect命令进行密码认证"
            # 注意：expect的-c选项不能很好地处理交互式命令
            # 对于SSH和SCP，我们需要使用expect脚本
            # 这里我们创建一个简单的expect包装函数
            # 由于expect -c在处理复杂命令时有限制，我们使用临时expect脚本
            RSYNC_CMD="rsync"
            # SSH和SCP命令将在需要时通过expect脚本执行
            # 这里先设置占位符，实际使用时会在expect脚本中处理
        fi
    else
        # 使用sshpass（sshpass已安装）
        SSH_CMD="sshpass -p '$SERVER_PASSWORD' ssh $SSH_OPTIONS"
        SCP_CMD="sshpass -p '$SERVER_PASSWORD' scp $SCP_OPTIONS"
        RSYNC_CMD="sshpass -p '$SERVER_PASSWORD' rsync"
    fi
else
    SSH_CMD="ssh $SSH_OPTIONS"
    SCP_CMD="scp $SCP_OPTIONS"
    RSYNC_CMD="rsync"
fi

# 检查SSH连接
print_info "检查SSH连接..."
if [ "$USE_PASSWORD" = true ] && [ "$USE_EXPECT" = true ] && [ ! -f "$SCRIPT_DIR/ssh_with_password.sh" ]; then
    # 如果使用expect但没有脚本，创建临时expect脚本用于SSH测试
    TEMP_SSH_TEST=$(mktemp)
    cat > "$TEMP_SSH_TEST" << 'EXPECT_SSH_EOF'
set timeout 10
set password [lindex $argv 0]
set ssh_options [lindex $argv 1]
set server_user [lindex $argv 2]
set server_host [lindex $argv 3]

# 正确展开SSH选项
if {[string length $ssh_options] > 0} {
    eval spawn ssh $ssh_options $server_user@$server_host exit
} else {
    spawn ssh $server_user@$server_host exit
}
expect {
    -re "(?i)password:" {
        send "$password\r"
        exp_continue
    }
    -re "yes/no" {
        send "yes\r"
        exp_continue
    }
    eof {
        catch wait result
        set exit_code [lindex $result 3]
        exit $exit_code
    }
    timeout {
        exit 1
    }
}
EXPECT_SSH_EOF
    if expect "$TEMP_SSH_TEST" "$SERVER_PASSWORD" "$SSH_OPTIONS" "$SERVER_USER" "$SERVER_HOST" 2>/dev/null; then
        print_info "SSH连接成功！"
        rm -f "$TEMP_SSH_TEST"
    else
        print_error "无法连接到服务器，请检查:"
        print_error "1. 服务器IP地址是否正确: $SERVER_HOST"
        print_error "2. 密码是否正确"
        print_error "3. 服务器是否允许SSH连接"
        rm -f "$TEMP_SSH_TEST"
        exit 1
    fi
elif [ "$USE_PASSWORD" = true ]; then
    # 使用sshpass的情况
    if ! eval "$SSH_CMD -o ConnectTimeout=5 $SERVER_USER@$SERVER_HOST 'exit'" 2>/dev/null; then
        print_error "无法连接到服务器，请检查:"
        print_error "1. 服务器IP地址是否正确: $SERVER_HOST"
        print_error "2. 密码是否正确"
        print_error "3. 服务器是否允许SSH连接"
        exit 1
    fi
else
    if ! eval "$SSH_CMD -o ConnectTimeout=5 -o BatchMode=yes $SERVER_USER@$SERVER_HOST 'exit'" 2>/dev/null; then
        print_error "无法连接到服务器，请检查:"
        print_error "1. 服务器IP地址是否正确: $SERVER_HOST"
        print_error "2. SSH密钥是否已配置"
        print_error "3. 服务器是否允许SSH连接"
        exit 1
    fi
fi

print_info "SSH连接成功！"

# 创建部署目录并安装必要工具
print_info "创建部署目录并检查必要工具..."
if [ "$USE_PASSWORD" = true ] && [ "$USE_EXPECT" = true ] && [ ! -f "$SCRIPT_DIR/ssh_with_password.sh" ]; then
    # 使用expect执行SSH命令
    TEMP_SSH_MKDIR=$(mktemp)
    cat > "$TEMP_SSH_MKDIR" << 'EXPECT_MKDIR_EOF'
set timeout 30
set password [lindex $argv 0]
set ssh_options [lindex $argv 1]
set server_user [lindex $argv 2]
set server_host [lindex $argv 3]
set deploy_path [lindex $argv 4]

# 正确展开SSH选项
if {[string length $ssh_options] > 0} {
    eval spawn ssh $ssh_options $server_user@$server_host "mkdir -p $deploy_path && (command -v rsync >/dev/null 2>&1 || yum install -y rsync 2>/dev/null || apt-get install -y rsync 2>/dev/null || true)"
} else {
    spawn ssh $server_user@$server_host "mkdir -p $deploy_path && (command -v rsync >/dev/null 2>&1 || yum install -y rsync 2>/dev/null || apt-get install -y rsync 2>/dev/null || true)"
}
expect {
    -re "(?i)password:" {
        send "$password\r"
        exp_continue
    }
    -re "yes/no" {
        send "yes\r"
        exp_continue
    }
    eof {
        catch wait result
        set exit_code [lindex $result 3]
        exit $exit_code
    }
    timeout {
        exit 1
    }
}
EXPECT_MKDIR_EOF
    expect "$TEMP_SSH_MKDIR" "$SERVER_PASSWORD" "$SSH_OPTIONS" "$SERVER_USER" "$SERVER_HOST" "$DEPLOY_PATH" || {
        print_error "创建部署目录失败"
        rm -f "$TEMP_SSH_MKDIR"
        exit 1
    }
    rm -f "$TEMP_SSH_MKDIR"
else
    eval "$SSH_CMD $SERVER_USER@$SERVER_HOST 'mkdir -p $DEPLOY_PATH && (command -v rsync >/dev/null 2>&1 || yum install -y rsync 2>/dev/null || apt-get install -y rsync 2>/dev/null || true)'"
fi

# 上传项目文件（排除node_modules, .git等）
print_info "上传项目文件..."
if [ "$USE_PASSWORD" = true ] && [ "$USE_EXPECT" = false ]; then
    # 使用sshpass时，rsync需要特殊处理
    # 转义密码中的特殊字符
    ESCAPED_PASSWORD=$(printf '%q' "$SERVER_PASSWORD")
    # 切换到项目根目录执行rsync
    cd "$PROJECT_ROOT"
    rsync -avz --progress \
        -e "sshpass -p $ESCAPED_PASSWORD ssh $SSH_OPTIONS" \
        --exclude 'node_modules' \
        --exclude 'node_modules/' \
        --exclude '*/node_modules' \
        --exclude '*/node_modules/' \
        --exclude '*/*/node_modules' \
        --exclude '*/*/node_modules/' \
        --exclude 'frontend/node_modules' \
        --exclude 'frontend/node_modules/' \
        --exclude '.git' \
        --exclude '.gitignore' \
        --exclude 'dist' \
        --exclude '__pycache__' \
        --exclude '*.pyc' \
        --exclude '.env' \
        --exclude '.env.local' \
        --exclude '.deploy.env' \
        --exclude '.vscode' \
        --exclude '.idea' \
        --exclude 'deploy' \
        --exclude 'logs' \
        --exclude 'logs/' \
        --exclude '*.log' \
        --exclude 'reports' \
        --exclude 'reports/' \
        --exclude 'cache' \
        --exclude 'cache/' \
        --exclude 'temp' \
        --exclude 'temp/' \
        --exclude 'venv' \
        --exclude 'venv/' \
        --exclude '.venv' \
        --exclude '.venv/' \
        --exclude 'ENV' \
        --exclude 'ENV/' \
        --exclude '.DS_Store' \
        --exclude 'test' \
        --exclude 'test/' \
        --exclude 'test*' \
        --exclude '*.egg-info' \
        --exclude '.pytest_cache' \
        ./ "$SERVER_USER@$SERVER_HOST:$DEPLOY_PATH/"
    cd "$SCRIPT_DIR"
elif [ "$USE_PASSWORD" = true ] && [ "$USE_EXPECT" = true ]; then
    # 使用expect时，需要创建一个expect包装脚本用于rsync
    # 创建临时expect脚本
    TEMP_EXPECT_SCRIPT=$(mktemp)
    cat > "$TEMP_EXPECT_SCRIPT" << 'EXPECT_EOF'
set timeout 600
set password [lindex $argv 0]
set ssh_options [lindex $argv 1]
set server_user [lindex $argv 2]
set server_host [lindex $argv 3]
set deploy_path [lindex $argv 4]
set project_root [lindex $argv 5]

spawn rsync -avz -e "ssh $ssh_options" \
    --exclude 'node_modules' \
    --exclude 'node_modules/' \
    --exclude '*/node_modules' \
    --exclude '*/node_modules/' \
    --exclude '*/*/node_modules' \
    --exclude '*/*/node_modules/' \
    --exclude 'frontend/node_modules' \
    --exclude 'frontend/node_modules/' \
    --exclude '.git' \
    --exclude '.gitignore' \
    --exclude 'dist' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '.env' \
    --exclude '.env.local' \
    --exclude '.deploy.env' \
    --exclude '.vscode' \
    --exclude '.idea' \
    --exclude 'deploy' \
    --exclude 'logs' \
    --exclude 'logs/' \
    --exclude '*.log' \
    --exclude 'reports' \
    --exclude 'reports/' \
    --exclude 'cache' \
    --exclude 'cache/' \
    --exclude 'temp' \
    --exclude 'temp/' \
    --exclude 'venv' \
    --exclude 'venv/' \
    --exclude '.venv' \
    --exclude '.venv/' \
    --exclude 'ENV' \
    --exclude 'ENV/' \
    --exclude '.DS_Store' \
    --exclude 'test' \
    --exclude 'test/' \
    --exclude 'test*' \
    --exclude '*.egg-info' \
    --exclude '.pytest_cache' \
    $project_root/ $server_user@$server_host:$deploy_path/

expect {
    -re "(?i)password:" {
        send "$password\r"
        exp_continue
    }
    -re "yes/no" {
        send "yes\r"
        exp_continue
    }
    eof {
        catch wait result
        set exit_code [lindex $result 3]
        exit $exit_code
    }
    timeout {
        puts "rsync timeout after 600 seconds"
        exit 1
    }
}
EXPECT_EOF
    
    # 执行expect脚本（传递项目根目录）
    expect "$TEMP_EXPECT_SCRIPT" "$SERVER_PASSWORD" "$SSH_OPTIONS" "$SERVER_USER" "$SERVER_HOST" "$DEPLOY_PATH" "$PROJECT_ROOT" || {
        print_error "expect脚本执行失败"
        rm -f "$TEMP_EXPECT_SCRIPT"
        exit 1
    }
    EXIT_CODE=$?
    rm -f "$TEMP_EXPECT_SCRIPT"
    
    if [ $EXIT_CODE -ne 0 ]; then
        print_error "rsync上传失败，退出码: $EXIT_CODE"
        exit 1
    fi
else
    # 使用密钥认证时，SSH选项必须通过-e参数传递给ssh
    # 切换到项目根目录执行rsync
    cd "$PROJECT_ROOT"
    rsync -avz --progress \
        -e "ssh $SSH_OPTIONS" \
        --exclude 'node_modules' \
        --exclude 'node_modules/' \
        --exclude '**/node_modules' \
        --exclude '**/node_modules/' \
        --exclude '.git' \
        --exclude '.gitignore' \
        --exclude 'dist' \
        --exclude '__pycache__' \
        --exclude '*.pyc' \
        --exclude '.env' \
        --exclude '.env.local' \
        --exclude '.deploy.env' \
        --exclude '.vscode' \
        --exclude '.idea' \
        --exclude 'deploy' \
        --exclude 'logs' \
        --exclude 'logs/' \
        --exclude '*.log' \
        --exclude 'reports' \
        --exclude 'reports/' \
        --exclude 'cache' \
        --exclude 'cache/' \
        --exclude 'temp' \
        --exclude 'temp/' \
        --exclude 'venv' \
        --exclude 'venv/' \
        --exclude '.venv' \
        --exclude '.venv/' \
        --exclude 'ENV' \
        --exclude 'ENV/' \
        --exclude '.DS_Store' \
        --exclude 'test' \
        --exclude 'test/' \
        --exclude 'test*' \
        --exclude '*.egg-info' \
        --exclude '.pytest_cache' \
        ./ "$SERVER_USER@$SERVER_HOST:$DEPLOY_PATH/"
    cd "$SCRIPT_DIR"
fi

# 上传部署脚本
print_info "上传服务器端部署脚本..."
if [ "$USE_PASSWORD" = true ] && [ "$USE_EXPECT" = true ] && [ ! -f "$SCRIPT_DIR/ssh_with_password.sh" ]; then
    # 使用expect上传文件
    TEMP_SCP=$(mktemp)
    cat > "$TEMP_SCP" << 'EXPECT_SCP_EOF'
set timeout 30
set password [lindex $argv 0]
set scp_options [lindex $argv 1]
set local_file [lindex $argv 2]
set remote_path [lindex $argv 3]

# 正确展开SCP选项
if {[string length $scp_options] > 0} {
    eval spawn scp $scp_options $local_file $remote_path
} else {
    spawn scp $local_file $remote_path
}
expect {
    -re "(?i)password:" {
        send "$password\r"
        exp_continue
    }
    -re "yes/no" {
        send "yes\r"
        exp_continue
    }
    eof {
        catch wait result
        set exit_code [lindex $result 3]
        exit $exit_code
    }
    timeout {
        exit 1
    }
}
EXPECT_SCP_EOF
    expect "$TEMP_SCP" "$SERVER_PASSWORD" "$SCP_OPTIONS" "$SCRIPT_DIR/server_deploy.sh" "$SERVER_USER@$SERVER_HOST:$DEPLOY_PATH/" || {
        print_error "上传server_deploy.sh失败"
        rm -f "$TEMP_SCP"
        exit 1
    }
    rm -f "$TEMP_SCP"
else
    eval "$SCP_CMD $SCRIPT_DIR/server_deploy.sh $SERVER_USER@$SERVER_HOST:$DEPLOY_PATH/"
fi

# 上传systemd服务文件（如果存在）
if [ -f "stock-scanner.service" ]; then
    print_info "上传systemd服务文件..."
    if [ "$USE_PASSWORD" = true ] && [ "$USE_EXPECT" = true ] && [ ! -f "$SCRIPT_DIR/ssh_with_password.sh" ]; then
        # 使用expect上传文件
        TEMP_SCP_SERVICE=$(mktemp)
        cat > "$TEMP_SCP_SERVICE" << 'EXPECT_SCP_SERVICE_EOF'
set timeout 30
set password [lindex $argv 0]
set scp_options [lindex $argv 1]
set local_file [lindex $argv 2]
set remote_path [lindex $argv 3]

# 正确展开SCP选项
if {[string length $scp_options] > 0} {
    eval spawn scp $scp_options $local_file $remote_path
} else {
    spawn scp $local_file $remote_path
}
expect {
    -re "(?i)password:" {
        send "$password\r"
        exp_continue
    }
    -re "yes/no" {
        send "yes\r"
        exp_continue
    }
    eof {
        catch wait result
        set exit_code [lindex $result 3]
        exit $exit_code
    }
    timeout {
        exit 1
    }
}
EXPECT_SCP_SERVICE_EOF
        expect "$TEMP_SCP_SERVICE" "$SERVER_PASSWORD" "$SCP_OPTIONS" "stock-scanner.service" "$SERVER_USER@$SERVER_HOST:/tmp/" || {
            print_error "上传stock-scanner.service失败"
            rm -f "$TEMP_SCP_SERVICE"
            exit 1
        }
        rm -f "$TEMP_SCP_SERVICE"
    else
        eval "$SCP_CMD stock-scanner.service $SERVER_USER@$SERVER_HOST:/tmp/"
    fi
fi

# 在服务器上执行部署脚本
print_info "在服务器上执行部署..."
if [ "$USE_PASSWORD" = true ] && [ "$USE_EXPECT" = true ] && [ ! -f "$SCRIPT_DIR/ssh_with_password.sh" ]; then
    # 使用expect执行远程命令
    TEMP_SSH_EXEC=$(mktemp)
    cat > "$TEMP_SSH_EXEC" << 'EXPECT_SSH_EXEC_EOF'
set timeout 600
set password [lindex $argv 0]
set ssh_options [lindex $argv 1]
set server_user [lindex $argv 2]
set server_host [lindex $argv 3]
set deploy_path [lindex $argv 4]

# 正确展开SSH选项
if {[string length $ssh_options] > 0} {
    eval spawn ssh $ssh_options $server_user@$server_host "cd $deploy_path && chmod +x server_deploy.sh && bash server_deploy.sh"
} else {
    spawn ssh $server_user@$server_host "cd $deploy_path && chmod +x server_deploy.sh && bash server_deploy.sh"
}
expect {
    -re "(?i)password:" {
        send "$password\r"
        exp_continue
    }
    -re "yes/no" {
        send "yes\r"
        exp_continue
    }
    eof {
        catch wait result
        set exit_code [lindex $result 3]
        exit $exit_code
    }
    timeout {
        puts "SSH执行超时"
        exit 1
    }
}
EXPECT_SSH_EXEC_EOF
    expect "$TEMP_SSH_EXEC" "$SERVER_PASSWORD" "$SSH_OPTIONS" "$SERVER_USER" "$SERVER_HOST" "$DEPLOY_PATH" || {
        print_error "执行server_deploy.sh失败"
        rm -f "$TEMP_SSH_EXEC"
        exit 1
    }
    rm -f "$TEMP_SSH_EXEC"
else
    eval "$SSH_CMD $SERVER_USER@$SERVER_HOST 'cd $DEPLOY_PATH && chmod +x server_deploy.sh && bash server_deploy.sh'"
fi

print_info "部署完成！"
print_info "前端访问地址: http://$SERVER_HOST:${FRONTEND_PORT:-80}/agent"
print_info "后端API地址: http://$SERVER_HOST:${BACKEND_PORT:-8001}"
print_info "API文档地址: http://$SERVER_HOST:${FRONTEND_PORT:-80}/api/docs"
