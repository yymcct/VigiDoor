#!/bin/bash
# VigiDoor 启动脚本

echo "🚀 启动 VigiDoor 智慧安防门..."

PROJECT_DIR="/home/yymcct/ws/VigiDoor"
cd "$PROJECT_DIR"

# 方式 1: 使用 systemd（推荐）
if command -v systemctl &> /dev/null; then
    echo "使用 systemd 启动服务..."
    sudo systemctl start vigidoor
    echo "✅ 服务已启动"
    echo ""
    echo "查看状态: sudo systemctl status vigidoor"
    echo "查看日志: sudo journalctl -u vigidoor -f"
else
    # 方式 2: 直接运行（开发模式）
    echo "使用直接模式启动..."
    
    # 激活虚拟环境
    if [ -d "venv" ]; then
        source venv/bin/activate
    fi
    
    # 运行 supervisor
    python3 supervisor.py
fi
