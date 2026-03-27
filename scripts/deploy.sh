#!/bin/bash
# ==============================================================================
# VigiDoor — 远程部署脚本（在开发机上执行）
#
# 用途：将源码同步到树莓派，并触发远程编译（可选）
#       如果不在树莓派上编译，也可仅同步源码 + 用 venv 运行
#
# 使用方式：
#   # 仅同步源码（源码模式部署）：
#   bash scripts/deploy.sh --host ubuntu@192.168.1.100
#
#   # 同步 + 触发远程 Nuitka 编译：
#   bash scripts/deploy.sh --host ubuntu@192.168.1.100 --build
#
#   # 同步预编译好的 release 包：
#   bash scripts/deploy.sh --host ubuntu@192.168.1.100 --release dist/vigidoor-release-*.tar.gz
# ==============================================================================

set -e

# ── 默认值 ────────────────────────────────────────────────────────────────────
SSH_HOST=""
REMOTE_DIR="/home/ubuntu/VigiDoor"
DO_BUILD=false
RELEASE_TARBALL=""

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# ── 参数解析 ─────────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --host)    SSH_HOST="$2";         shift 2 ;;
        --dir)     REMOTE_DIR="$2";       shift 2 ;;
        --build)   DO_BUILD=true;         shift 1 ;;
        --release) RELEASE_TARBALL="$2";  shift 2 ;;
        *) error "未知参数: $1" ;;
    esac
done

[ -z "$SSH_HOST" ] && error "请指定树莓派地址: --host user@ip"

# ── 模式1: 同步 release 包 ───────────────────────────────────────────────────
if [ -n "$RELEASE_TARBALL" ]; then
    [ -f "$RELEASE_TARBALL" ] || error "release 包不存在: $RELEASE_TARBALL"
    info "上传 release 包到 $SSH_HOST:$REMOTE_DIR ..."

    ssh "$SSH_HOST" "mkdir -p $REMOTE_DIR"
    scp "$RELEASE_TARBALL" "$SSH_HOST:/tmp/vigidoor-release.tar.gz"
    ssh "$SSH_HOST" "
        set -e
        cd $REMOTE_DIR
        tar -xzf /tmp/vigidoor-release.tar.gz --strip-components=1
        chmod +x vigidoor
        # 注册/重启服务
        sudo cp scripts/vigidoor.service /etc/systemd/system/ 2>/dev/null || true
        sudo sed -i 's|ExecStart=.*|ExecStart=$REMOTE_DIR/vigidoor|' /etc/systemd/system/vigidoor.service || true
        sudo systemctl daemon-reload || true
        sudo systemctl restart vigidoor || true
        echo 'release 部署完成'
    "
    info "✅ release 部署完成"
    exit 0
fi

# ── 模式2: 同步源码（rsync）────────────────────────────────────────────────
info "同步源码到 $SSH_HOST:$REMOTE_DIR ..."

ssh "$SSH_HOST" "mkdir -p $REMOTE_DIR"

rsync -avz --progress \
    --exclude='.venv/' \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    --exclude='*.pyo' \
    --exclude='dist/' \
    --exclude='logs/' \
    --exclude='data/recordings/' \
    --exclude='data/snapshots/' \
    --exclude='data/cache/' \
    --exclude='.git/' \
    --exclude='*.egg-info/' \
    ./ "$SSH_HOST:$REMOTE_DIR/"

info "✅ 源码同步完成"

# ── 模式3: 同步后触发远程 Nuitka 编译 ─────────────────────────────────────
if $DO_BUILD; then
    info "在树莓派上执行 Nuitka 编译（可能需要 10~30 分钟）..."
    ssh -t "$SSH_HOST" "
        set -e
        cd $REMOTE_DIR
        # 安装/更新依赖
        source .venv/bin/activate
        pip install -q -r requirements.txt
        # 执行编译
        bash scripts/build_nuitka.sh
    "
    info "✅ 远程编译完成"
else
    # 仅源码模式：确保依赖已安装，重启服务
    info "源码模式：同步依赖并重启服务..."
    ssh -t "$SSH_HOST" "
        set -e
        cd $REMOTE_DIR
        source .venv/bin/activate 2>/dev/null || python3 -m venv .venv && source .venv/bin/activate
        pip install -q -r requirements.txt
        sudo systemctl restart vigidoor 2>/dev/null || python3 supervisor.py &
        echo '服务已重启'
    "
    info "✅ 源码部署完成"
fi
