#!/bin/bash
# VigiDoor 开发模式启动脚本（不使用 systemd）

echo "🔧 开发模式启动 VigiDoor..."

PROJECT_DIR="/home/yymcct/ws/VigiDoor"
cd "$PROJECT_DIR"

# 激活虚拟环境（如果存在）
if [ -d "venv" ]; then
    echo "激活虚拟环境..."
    source venv/bin/activate
fi

# 直接运行 supervisor
echo "启动 Supervisor..."
python3 supervisor.py
