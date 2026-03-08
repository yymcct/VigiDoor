# huaweiIOT 转发平台

华为云 IoT 推流控制服务，提供 RESTful API 接口，通过华为云 IoTDA 服务向设备发送推流控制命令。

## 功能特性

### 核心功能
- ✅ 基于华为云 IoTDA SDK 的设备命令下发
- ✅ 推流开始/停止控制
- ✅ ZLMediaKit Webhook 按需推流（on_stream_not_found / on_stream_none_reader）
- ✅ RESTful API 接口
- ✅ 支持自定义 RTMP 推流地址
- ✅ Docker 容器化部署
- ✅ 健康检查接口
- ✅ 完整的日志记录

### 🆕 WebSocket 语音中继功能
- ✨ **实时语音通话**：浏览器 ↔ 树莓派双向音频通信
- ✨ **按需连接**：节省资源，支持动态会话管理
- ✨ **智能路由**：基于 Socket.IO 的高性能消息转发
- ✨ **稳定可靠**：超时管理、心跳保活、自动清理
- ✨ **易于集成**：完善的 REST API 和 WebSocket 事件协议

📚 **详细文档**：
- [快速开始指南](docs/QUICKSTART.md) - 10分钟快速上手
- [WebSocket 功能文档](docs/WEBSOCKET_VOICE.md) - 完整的 API 和事件协议
- [架构设计文档](docs/ARCHITECTURE.md) - 架构评审和设计方案

## 快速开始

### 本地运行

```
python3 -m venv .venv

source .venv/bin/activate
```

1. 安装依赖：
```bash
pip install -r requirements.txt
```

2. 配置环境变量：
```bash
cp .env.example .env
# 编辑 .env 文件，填写华为云配置
```

3. 运行服务：
```bash
make dev
# 或直接运行
python main.py
```

服务启动后，访问：
- REST API: `http://localhost:5002/api/v1/`
- WebSocket: `ws://localhost:5002`
- 健康检查: `http://localhost:5002/health`

### Docker 部署（推荐）

详细的 Docker 部署说明请参考 [README_DOCKER.md](README_DOCKER.md)

### 快速测试 WebSocket 功能

```bash
# 安装测试依赖
pip install python-socketio[client]

# 运行自动化测试
python tests/test_websocket_client.py scenario1
```

👉 更多测试方法请参考 [快速开始指南](docs/QUICKSTART.md)



