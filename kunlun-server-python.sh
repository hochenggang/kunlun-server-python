#!/bin/bash

set -e

APP_NAME="kunlun-server-python"
APP_DIR="/opt/apps/$APP_NAME"
SERVICE_FILE="/etc/systemd/system/$APP_NAME.service"
REPO_URL="https://github.com/hochenggang/kunlun-server-python.git"
ENV_FILE="$APP_DIR/.env"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

print_banner() {
    echo -e "${BLUE}"
    echo "=========================================="
    echo "    Kunlun Server 管理脚本"
    echo "=========================================="
    echo -e "${NC}"
}

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

get_admin_token() {
    if [[ -f "$ENV_FILE" ]]; then
        ADMIN_TOKEN=$(grep "^ADMIN_TOKEN=" "$ENV_FILE" | cut -d'=' -f2)
    fi
    
    if [[ -z "$ADMIN_TOKEN" ]]; then
        print_error "未找到 ADMIN_TOKEN，请检查 $ENV_FILE"
        exit 1
    fi
}

get_service_port() {
    SERVICE_PORT=8008
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "此操作需要 root 权限"
        print_info "请使用: sudo $0 $1"
        exit 1
    fi
}

check_dependencies() {
    print_info "检查依赖..."
    local missing=()
    
    for cmd in python3 git curl; do
        if ! command -v $cmd &> /dev/null; then
            missing+=($cmd)
        fi
    done
    
    if [[ ${#missing[@]} -gt 0 ]]; then
        print_error "缺少以下依赖: ${missing[*]}"
        print_info "请先安装缺少的依赖"
        exit 1
    fi
    
    print_info "依赖检查通过"
}

check_service_running() {
    if ! systemctl is-active --quiet "$APP_NAME"; then
        print_error "服务未运行"
        print_info "请先启动服务: systemctl start $APP_NAME"
        exit 1
    fi
}

show_help() {
    print_banner
    echo "用法: $0 <命令> [参数]"
    echo ""
    echo -e "${CYAN}服务管理:${NC}"
    echo "  install              交互式安装服务"
    echo "  uninstall            卸载服务并删除所有数据"
    echo "  status               查看服务状态"
    echo "  start                启动服务"
    echo "  stop                 停止服务"
    echo "  restart              重启服务"
    echo "  logs                 查看服务日志"
    echo ""
    echo -e "${CYAN}客户端管理:${NC}"
    echo "  client list          查看所有客户端"
    echo "  client pending       查看待审核客户端 (status=0)"
    echo "  client approve <id>  审核通过客户端 (设置 status=1)"
    echo "  client reject <id>   拒绝客户端 (设置 status=0)"
    echo "  client delete <id>   删除客户端及所有关联数据"
    echo "  client info <id>     查看客户端详情"
    echo ""
    echo -e "${CYAN}其他:${NC}"
    echo "  help                 显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0 install"
    echo "  $0 client list"
    echo "  $0 client approve 1"
    echo "  $0 client delete 2"
}

get_user_input() {
    echo ""
    echo -e "${YELLOW}请配置安装参数:${NC}"
    echo ""
    
    read -p "安装目录 [默认: $APP_DIR]: " custom_dir
    APP_DIR=${custom_dir:-$APP_DIR}
    ENV_FILE="$APP_DIR/.env"
    
    while true; do
        read -p "设置管理员 Token (ADMIN_TOKEN): " admin_token
        if [[ -n "$admin_token" ]]; then
            break
        fi
        print_warn "Token 不能为空，请重新输入"
    done
    
    read -p "服务端口 [默认: 8008]: " service_port
    SERVICE_PORT=${service_port:-8008}
    
    echo ""
    echo -e "${YELLOW}配置确认:${NC}"
    echo "  安装目录: $APP_DIR"
    echo "  管理员 Token: $admin_token"
    echo "  服务端口: $SERVICE_PORT"
    echo ""
    
    read -p "确认安装? [Y/n]: " confirm
    if [[ "$confirm" =~ ^[Nn]$ ]]; then
        print_info "安装已取消"
        exit 0
    fi
}

create_user() {
    if id "$APP_NAME" &>/dev/null; then
        print_info "用户 $APP_NAME 已存在"
    else
        print_info "创建专用用户 $APP_NAME..."
        useradd -r -s /usr/sbin/nologin -M "$APP_NAME"
        print_info "用户创建成功"
    fi
}

deploy_code() {
    print_info "部署代码..."
    
    if [[ -d "$APP_DIR" ]]; then
        print_warn "目录 $APP_DIR 已存在"
        read -p "是否删除并重新安装? [y/N]: " reinstall
        if [[ "$reinstall" =~ ^[Yy]$ ]]; then
            rm -rf "$APP_DIR"
        else
            print_error "安装目录已存在，请手动处理"
            exit 1
        fi
    fi
    
    mkdir -p "$APP_DIR"
    cd "$APP_DIR"
    
    print_info "克隆代码仓库..."
    git clone "$REPO_URL" .
    
    print_info "代码部署完成"
}

setup_venv() {
    print_info "创建虚拟环境..."
    cd "$APP_DIR"
    python3 -m venv venv
    source venv/bin/activate
    
    print_info "安装依赖..."
    pip install -r requirements.txt
    
    print_info "虚拟环境配置完成"
}

create_directories() {
    print_info "创建必要目录..."
    mkdir -p "$APP_DIR/db"
}

create_env_file() {
    print_info "创建环境变量文件..."
    cat > "$APP_DIR/.env" << EOF
ADMIN_TOKEN=$admin_token
EOF
    print_info ".env 文件创建成功"
}

set_permissions() {
    print_info "设置目录权限..."
    chown -R "$APP_NAME:$APP_NAME" "$APP_DIR"
    chmod 600 "$APP_DIR/.env"
    print_info "权限设置完成"
}

create_service() {
    print_info "创建 systemd 服务..."
    
    cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Kunlun Server - Server Monitoring Backend
After=network.target

[Service]
User=$APP_NAME
Group=$APP_NAME
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin"
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/venv/bin/python app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
    
    print_info "服务文件创建成功"
}

start_service() {
    print_info "重新加载 systemd..."
    systemctl daemon-reload
    
    print_info "启动服务..."
    systemctl start "$APP_NAME"
    
    print_info "设置开机自启..."
    systemctl enable "$APP_NAME"
    
    print_info "服务启动成功"
}

verify_installation() {
    echo ""
    print_info "验证安装..."
    
    if systemctl is-active --quiet "$APP_NAME"; then
        print_info "服务状态: ${GREEN}运行中${NC}"
    else
        print_error "服务状态: 未运行"
        print_info "请检查日志: journalctl -u $APP_NAME -n 50"
    fi
    
    if curl -s "http://localhost:$SERVICE_PORT/status" | grep -q "kunlun"; then
        print_info "API 测试: ${GREEN}成功${NC}"
    else
        print_warn "API 测试: 失败 (服务可能还在启动中)"
    fi
}

print_summary() {
    echo ""
    echo -e "${GREEN}=========================================="
    echo "    安装完成!"
    echo "==========================================${NC}"
    echo ""
    echo "访问地址: http://<server-ip>:$SERVICE_PORT"
    echo ""
    echo "常用命令:"
    echo "  查看状态: $0 status"
    echo "  查看日志: $0 logs"
    echo "  查看客户端: $0 client list"
    echo "  审核客户端: $0 client approve <id>"
    echo ""
}

do_install() {
    check_root "install"
    check_dependencies
    get_user_input
    
    echo ""
    print_info "开始安装..."
    echo ""
    
    create_user
    deploy_code
    setup_venv
    create_directories
    create_env_file
    set_permissions
    create_service
    start_service
    verify_installation
    print_summary
}

do_uninstall() {
    check_root "uninstall"
    print_banner
    echo -e "${YELLOW}卸载 Kunlun Server${NC}"
    echo ""
    
    read -p "确认卸载? 这将删除所有数据! [y/N]: " confirm
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        print_info "卸载已取消"
        exit 0
    fi
    
    print_info "停止服务..."
    systemctl stop "$APP_NAME" 2>/dev/null || true
    systemctl disable "$APP_NAME" 2>/dev/null || true
    
    print_info "删除服务文件..."
    rm -f "$SERVICE_FILE"
    systemctl daemon-reload
    
    print_info "删除用户..."
    userdel "$APP_NAME" 2>/dev/null || true
    
    print_info "删除安装目录..."
    rm -rf "$APP_DIR"
    
    echo ""
    print_info "卸载完成"
}

do_status() {
    print_banner
    if systemctl is-active --quiet "$APP_NAME"; then
        echo -e "服务状态: ${GREEN}运行中${NC}"
    else
        echo -e "服务状态: ${RED}未运行${NC}"
    fi
    echo ""
    systemctl status "$APP_NAME" --no-pager || true
}

do_start() {
    check_root "start"
    print_info "启动服务..."
    systemctl start "$APP_NAME"
    print_info "服务已启动"
}

do_stop() {
    check_root "stop"
    print_info "停止服务..."
    systemctl stop "$APP_NAME"
    print_info "服务已停止"
}

do_restart() {
    check_root "restart"
    print_info "重启服务..."
    systemctl restart "$APP_NAME"
    print_info "服务已重启"
}

do_logs() {
    journalctl -u "$APP_NAME" -f
}

api_request() {
    local method=$1
    local endpoint=$2
    local data=$3
    
    get_admin_token
    get_service_port
    
    local url="http://localhost:$SERVICE_PORT$endpoint"
    
    if [[ -n "$data" ]]; then
        curl -s -X "$method" \
            -H "Authorization: $ADMIN_TOKEN" \
            -H "Content-Type: application/json" \
            -d "$data" \
            "$url"
    else
        curl -s -X "$method" \
            -H "Authorization: $ADMIN_TOKEN" \
            "$url"
    fi
}

do_client_list() {
    check_service_running
    print_info "获取客户端列表..."
    echo ""
    
    local response=$(api_request "GET" "/admin/client")
    
    if command -v jq &> /dev/null; then
        echo "$response" | jq -r '.[] | "\(.id)\t\(.machine_id[0:12])...\t\(.hostname)\t\(.status)\t\(.ip // "N/A")\t\(.last_update)"' | column -t -s $'\t'
        echo ""
        echo -e "${CYAN}ID\tMACHINE_ID\t\tHOSTNAME\t\tSTATUS\tIP\t\tLAST_UPDATE${NC}"
    else
        echo "$response" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f'ID    MACHINE_ID        HOSTNAME            STATUS    IP              LAST_UPDATE')
print('-' * 80)
for c in data:
    mid = c.get('machine_id', '')[:12] + '...'
    print(f\"{c['id']:<5} {mid:<16} {c.get('hostname', 'N/A'):<20} {c.get('status', 'N/A'):<8} {c.get('ip', 'N/A'):<16} {c.get('last_update', 'N/A')}\")
"
    fi
}

do_client_pending() {
    check_service_running
    print_info "获取待审核客户端..."
    echo ""
    
    local response=$(api_request "GET" "/admin/client")
    
    if command -v jq &> /dev/null; then
        local pending=$(echo "$response" | jq '[.[] | select(.status == 0)]')
        local count=$(echo "$pending" | jq 'length')
        
        if [[ "$count" -eq 0 ]]; then
            print_info "没有待审核的客户端"
        else
            echo -e "${YELLOW}待审核客户端 ($count):${NC}"
            echo "$pending" | jq -r '.[] | "  ID: \(.id), MachineID: \(.machine_id[0:12])..., Hostname: \(.hostname), IP: \(.ip // "N/A")"'
        fi
    else
        echo "$response" | python3 -c "
import sys, json
data = json.load(sys.stdin)
pending = [c for c in data if c.get('status') == 0]
if not pending:
    print('没有待审核的客户端')
else:
    print(f'待审核客户端 ({len(pending)}):')
    for c in pending:
        mid = c.get('machine_id', '')[:12] + '...'
        print(f\"  ID: {c['id']}, MachineID: {mid}, Hostname: {c.get('hostname', 'N/A')}, IP: {c.get('ip', 'N/A')}\")
"
    fi
}

do_client_approve() {
    check_service_running
    local client_id=$1
    
    if [[ -z "$client_id" ]]; then
        print_error "请指定客户端 ID"
        print_info "用法: $0 client approve <id>"
        exit 1
    fi
    
    print_info "审核通过客户端 $client_id..."
    
    local response=$(api_request "PUT" "/admin/client/$client_id" '{"status": 1}')
    
    if echo "$response" | grep -q '"ok"[[:space:]]*:[[:space:]]*true'; then
        print_info "客户端 $client_id 已审核通过"
    else
        print_error "操作失败: $response"
    fi
}

do_client_reject() {
    check_service_running
    local client_id=$1
    
    if [[ -z "$client_id" ]]; then
        print_error "请指定客户端 ID"
        print_info "用法: $0 client reject <id>"
        exit 1
    fi
    
    print_info "拒绝客户端 $client_id..."
    
    local response=$(api_request "PUT" "/admin/client/$client_id" '{"status": 0}')
    
    if echo "$response" | grep -q '"ok"[[:space:]]*:[[:space:]]*true'; then
        print_info "客户端 $client_id 已设置为待审核状态"
    else
        print_error "操作失败: $response"
    fi
}

do_client_delete() {
    check_service_running
    local client_id=$1
    
    if [[ -z "$client_id" ]]; then
        print_error "请指定客户端 ID"
        print_info "用法: $0 client delete <id>"
        exit 1
    fi
    
    echo -e "${YELLOW}警告: 这将删除客户端 $client_id 及所有关联数据!${NC}"
    read -p "确认删除? [y/N]: " confirm
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        print_info "操作已取消"
        exit 0
    fi
    
    print_info "删除客户端 $client_id..."
    
    local response=$(api_request "DELETE" "/admin/client/$client_id")
    
    if echo "$response" | grep -q '"ok"[[:space:]]*:[[:space:]]*true'; then
        print_info "客户端 $client_id 已删除"
    else
        print_error "操作失败: $response"
    fi
}

do_client_info() {
    check_service_running
    local client_id=$1
    
    if [[ -z "$client_id" ]]; then
        print_error "请指定客户端 ID"
        print_info "用法: $0 client info <id>"
        exit 1
    fi
    
    print_info "获取客户端 $client_id 详情..."
    echo ""
    
    local response=$(api_request "GET" "/admin/client")
    
    if command -v jq &> /dev/null; then
        echo "$response" | jq ".[] | select(.id == $client_id)"
    else
        echo "$response" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for c in data:
    if c.get('id') == $client_id:
        for k, v in c.items():
            print(f'{k}: {v}')
        break
else:
    print('客户端不存在')
"
    fi
}

handle_client() {
    local action=$1
    local arg=$2
    
    case "$action" in
        list)
            do_client_list
            ;;
        pending)
            do_client_pending
            ;;
        approve)
            do_client_approve "$arg"
            ;;
        reject)
            do_client_reject "$arg"
            ;;
        delete)
            do_client_delete "$arg"
            ;;
        info)
            do_client_info "$arg"
            ;;
        *)
            print_error "未知命令: client $action"
            echo ""
            echo "可用命令:"
            echo "  client list          查看所有客户端"
            echo "  client pending       查看待审核客户端"
            echo "  client approve <id>  审核通过客户端"
            echo "  client reject <id>   拒绝客户端"
            echo "  client delete <id>   删除客户端"
            echo "  client info <id>     查看客户端详情"
            exit 1
            ;;
    esac
}

main() {
    local command=$1
    shift || true
    
    case "$command" in
        install)
            do_install
            ;;
        uninstall)
            do_uninstall
            ;;
        status)
            do_status
            ;;
        start)
            do_start
            ;;
        stop)
            do_stop
            ;;
        restart)
            do_restart
            ;;
        logs)
            do_logs
            ;;
        client)
            handle_client "$@"
            ;;
        help|--help|-h)
            show_help
            ;;
        "")
            show_help
            ;;
        *)
            print_error "未知命令: $command"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

main "$@"
