#!/bin/bash
# VigiDoor 安装脚本

set -e

echo "======================================"
echo "   VigiDoor 智慧安防门 安装脚本"
echo "======================================"

# 检查是否为 root 用户
if [ "$EUID" -ne 0 ]; then
    echo "请使用 sudo 运行此脚本"
    exit 1
fi

# 项目根目录
PROJECT_DIR="/home/yymcct/ws/VigiDoor"

echo ""
echo "[1/5] 安装系统依赖..."
apt-get update
apt-get install -y python3 python3-pip python3-venv

echo ""
echo "[2/5] 创建虚拟环境..."
cd "$PROJECT_DIR"
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

echo ""
echo "[3/5] 安装 Python 依赖..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "[4/5] 创建必要目录..."
mkdir -p logs
mkdir -p data/snapshots
mkdir -p data/cache
mkdir -p models

echo ""
echo "[5/5] 安装 systemd 服务..."
cp scripts/vigidoor.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable vigidoor.service

echo ""
echo "======================================"
echo "   ✅ 安装完成！"
echo "======================================"
echo ""
echo "使用以下命令管理服务："
echo "  启动: sudo systemctl start vigidoor"
echo "  停止: sudo systemctl stop vigidoor"
echo "  状态: sudo systemctl status vigidoor"
echo "  日志: sudo journalctl -u vigidoor -f"
echo ""
echo "或使用快捷脚本："
echo "  启动: ./scripts/start.sh"
echo "  停止: ./scripts/stop.sh"
echo ""
