#!/bin/bash
# VigiDoor 停止脚本

echo "🛑 停止 VigiDoor 智慧安防门..."

# 方式 1: 使用 systemd
if command -v systemctl &> /dev/null; then
    sudo systemctl stop vigidoor
    echo "✅ 服务已停止"
else
    # 方式 2: 查找进程并杀死
    echo "查找并终止进程..."
    pkill -f "python3.*supervisor.py"
    echo "✅ 进程已终止"
fi
