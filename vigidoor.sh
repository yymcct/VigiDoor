#!/bin/bash
# VigiDoor 快捷命令脚本

print_header() {
    echo ""
    echo "╔════════════════════════════════════════════════════════╗"
    echo "║          VigiDoor 智慧安防门 - 命令菜单                ║"
    echo "╚════════════════════════════════════════════════════════╝"
    echo ""
}

print_usage() {
    echo "使用方法: ./vigidoor.sh <命令>"
    echo ""
    echo "可用命令:"
    echo ""
    echo "  📦 安装与部署:"
    echo "    install       安装系统服务（需要 sudo）"
    echo "    uninstall     卸载系统服务（需要 sudo）"
    echo ""
    echo "  🚀 启动与停止:"
    echo "    start         启动服务（systemd 模式）"
    echo "    stop          停止服务"
    echo "    restart       重启服务"
    echo "    dev           开发模式启动（前台运行）"
    echo ""
    echo "  📊 监控与调试:"
    echo "    status        查看服务状态"
    echo "    logs          查看实时日志"
    echo "    test          运行系统测试"
    echo ""
    echo "  🧹 维护:"
    echo "    clean         清理日志和缓存文件"
    echo "    deps          安装 Python 依赖"
    echo ""
}

case "$1" in
    install)
        echo "📦 安装系统服务..."
        sudo ./scripts/install.sh
        ;;
    
    uninstall)
        echo "🗑️  卸载系统服务..."
        sudo systemctl stop vigidoor 2>/dev/null
        sudo systemctl disable vigidoor 2>/dev/null
        sudo rm -f /etc/systemd/system/vigidoor.service
        sudo systemctl daemon-reload
        echo "✅ 卸载完成"
        ;;
    
    start)
        echo "🚀 启动服务..."
        ./scripts/start.sh
        ;;
    
    stop)
        echo "🛑 停止服务..."
        ./scripts/stop.sh
        ;;
    
    restart)
        echo "🔄 重启服务..."
        ./scripts/stop.sh
        sleep 2
        ./scripts/start.sh
        ;;
    
    dev)
        echo "🔧 开发模式启动..."
        ./scripts/dev_start.sh
        ;;
    
    status)
        if command -v systemctl &> /dev/null; then
            systemctl status vigidoor
        else
            ps aux | grep supervisor.py | grep -v grep
        fi
        ;;
    
    logs)
        echo "📝 查看实时日志（按 Ctrl+C 退出）..."
        if command -v systemctl &> /dev/null; then
            sudo journalctl -u vigidoor -f
        else
            tail -f logs/*.log
        fi
        ;;
    
    test)
        echo "🧪 运行系统测试..."
        python3 test_system.py
        ;;
    
    clean)
        echo "🧹 清理日志和缓存..."
        rm -rf logs/*.log
        rm -rf data/cache/*
        echo "✅ 清理完成"
        ;;
    
    deps)
        echo "📦 安装 Python 依赖..."
        pip3 install -r requirements.txt
        echo "✅ 依赖安装完成"
        ;;
    
    *)
        print_header
        print_usage
        exit 1
        ;;
esac
