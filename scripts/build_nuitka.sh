#!/bin/bash
# ==============================================================================
# VigiDoor — Nuitka 编译脚本（在树莓派上执行）
#
# 用途：将 Python 源码编译为原生二进制，提升性能并保护源码
# 要求：在目标树莓派上运行（ARM 架构），需先激活 venv
#
# 使用方式：
#   cd /home/ubuntu/VigiDoor
#   source .venv/bin/activate
#   bash scripts/build_nuitka.sh
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
OUTPUT_DIR="$PROJECT_ROOT/dist"
BUILD_LOG="$PROJECT_ROOT/logs/build_nuitka.log"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()    { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

cd "$PROJECT_ROOT"

# ── 1. 检查环境 ──────────────────────────────────────────────────────────────
info "检查编译环境..."

python3 -c "import sys; assert sys.version_info >= (3,8), 'Python 3.8+ required'" \
    || error "Python 版本不足，需要 3.8+"

if ! python3 -c "import nuitka" 2>/dev/null; then
    warn "未检测到 nuitka，正在安装..."
    pip install nuitka ordered-set
fi

# 检查 C 编译器（Nuitka 依赖 gcc）
command -v gcc >/dev/null 2>&1 || {
    warn "未检测到 gcc，正在安装..."
    sudo apt-get install -y gcc patchelf ccache
}

# ── 2. 准备目录 ──────────────────────────────────────────────────────────────
info "准备输出目录: $OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR" "$PROJECT_ROOT/logs"

# ── 3. 执行 Nuitka 编译 ───────────────────────────────────────────────────────
info "开始 Nuitka 编译（耗时较长，树莓派约 10~30 分钟）..."
info "编译日志: $BUILD_LOG"

# 检测 ccache 加速（二次编译更快）
CCACHE_FLAG=""
if command -v ccache >/dev/null 2>&1; then
    CCACHE_FLAG="--clang"
    info "检测到 ccache，启用编译缓存加速"
fi

python3 -m nuitka \
    --standalone \
    --onefile \
    --follow-imports \
    \
    `# ── 项目内部包 ──` \
    --include-package=core \
    --include-package=modules \
    --include-package=db \
    --include-package=utils \
    \
    `# ── 关键第三方包（standalone 模式有时需要显式指定）──` \
    --include-package=yaml \
    --include-package=paho \
    --include-package=psutil \
    --include-package=dateutil \
    --include-package=socketio \
    --include-package=websocket \
    --include-package=opuslib \
    --include-package=scipy \
    \
    `# ── 数据文件：随二进制一起打包 ──` \
    --include-data-files=config.yaml=config.yaml \
    --include-data-dir=assets=assets \
    --include-data-dir=models=models \
    --include-data-dir=certs=certs \
    \
    `# ── 插件：multiprocessing 必须启用，否则 spawn 子进程会崩溃 ──` \
    --enable-plugin=multiprocessing \
    \
    `# ── 优化选项 ──` \
    --python-flag=no_site \
    --python-flag=no_docstrings \
    --python-flag=-O \
    \
    `# ── 输出配置 ──` \
    --output-dir="$OUTPUT_DIR" \
    --output-filename=vigidoor \
    --remove-output \
    \
    supervisor.py 2>&1 | tee "$BUILD_LOG"

# ── 4. 整理输出 ──────────────────────────────────────────────────────────────
BINARY="$OUTPUT_DIR/vigidoor"
if [ ! -f "$BINARY" ]; then
    error "编译失败，未找到输出文件: $BINARY"
fi

# 赋予执行权限
chmod +x "$BINARY"

BINARY_SIZE=$(du -sh "$BINARY" | cut -f1)
info "✅ 编译成功: $BINARY ($BINARY_SIZE)"

# ── 5. 打包部署产物 ───────────────────────────────────────────────────────────
info "打包部署产物..."

RELEASE_DIR="$OUTPUT_DIR/release"
rm -rf "$RELEASE_DIR"
mkdir -p "$RELEASE_DIR"

# 拷贝二进制
cp "$BINARY" "$RELEASE_DIR/vigidoor"

# 拷贝运行时必须的目录（数据目录不打包，运行时自动创建）
cp config.yaml       "$RELEASE_DIR/"
cp -r assets/        "$RELEASE_DIR/assets/"
cp -r models/        "$RELEASE_DIR/models/"
cp -r certs/         "$RELEASE_DIR/certs/"
cp -r scripts/       "$RELEASE_DIR/scripts/"

# scripts/vigidoor.service 需要指向新的二进制路径，生成部署版
sed "s|/home/ubuntu/VigiDoor/.venv/bin/python -u /home/ubuntu/VigiDoor/supervisor.py|/home/ubuntu/VigiDoor/vigidoor|g" \
    scripts/vigidoor.service > "$RELEASE_DIR/scripts/vigidoor.service"

# 压缩
TARBALL="$OUTPUT_DIR/vigidoor-release-$(date +%Y%m%d_%H%M%S).tar.gz"
tar -czf "$TARBALL" -C "$OUTPUT_DIR" release/
TARBALL_SIZE=$(du -sh "$TARBALL" | cut -f1)

info "✅ 部署包生成: $TARBALL ($TARBALL_SIZE)"
info ""
info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
info "编译完成！后续步骤："
info "  1. 解压到目标目录:"
info "       tar -xzf $TARBALL -C /home/ubuntu/VigiDoor/"
info "  2. 安装 systemd 服务:"
info "       sudo cp release/scripts/vigidoor.service /etc/systemd/system/"
info "       sudo systemctl daemon-reload"
info "       sudo systemctl enable vigidoor"
info "       sudo systemctl start vigidoor"
info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
