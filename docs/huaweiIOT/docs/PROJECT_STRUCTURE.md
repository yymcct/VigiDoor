# 📂 项目结构说明

本文档说明 WebSocket 语音中继功能添加后的完整项目结构。

```
/home/ubuntu/VigiDoor/docs/huaweiIOT/
│
├── 📄 main.py                      # 应用入口（已更新，使用 SocketIO 运行）
├── 📄 requirements.txt             # Python 依赖（已更新，添加 WebSocket 库）
├── 📄 README.md                    # 项目主文档（已更新）
├── 📄 Dockerfile                   # Docker 镜像构建
├── 📄 docker-compose.yml           # Docker Compose 配置
├── 📄 Makefile                     # 便捷命令
│
├── 📁 app/                         # 应用核心代码
│   ├── __init__.py                 # Flask 应用工厂（已更新，集成 SocketIO）
│   ├── config.py                   # 配置管理（已更新，添加 WebSocket 配置）
│   │
│   ├── 📁 routes/                  # 路由层（API 接口）
│   │   ├── __init__.py
│   │   ├── health.py               # 健康检查
│   │   ├── stream.py               # 推流控制
│   │   ├── zlm_webhook.py          # ZLM Webhook
│   │   └── 🆕 voice.py             # 语音呼叫 API（新增）
│   │
│   └── 📁 services/                # 服务层（业务逻辑）
│       ├── __init__.py
│       ├── iotda.py                # 华为云 IoTDA 客户端
│       ├── 🆕 voice_session.py     # 语音会话管理器（新增）
│       └── 🆕 websocket_handler.py # WebSocket 事件处理器（新增）
│
├── 📁 tests/                       # 测试文件
│   ├── api_test.http               # REST API 测试（现有）
│   ├── 🆕 voice_test.http          # 语音 API 测试（新增）
│   └── 🆕 test_websocket_client.py # WebSocket 测试客户端（新增）
│
├── 📁 docs/                        # 📚 文档目录（新增）
│   ├── 🆕 QUICKSTART.md            # 快速开始指南
│   ├── 🆕 WEBSOCKET_VOICE.md       # WebSocket 功能完整文档
│   ├── 🆕 ARCHITECTURE.md          # 架构设计与评审
│   ├── 🆕 ROADMAP.md               # 实施路线图
│   └── 🆕 PROJECT_STRUCTURE.md     # 本文件
│
└── 📁 logs/                        # 日志目录
    └── app.log                     # 应用日志
```

---

## 🆕 新增文件详解

### 1. 核心业务代码

#### `app/services/voice_session.py`
**功能**：语音会话管理器
- ✅ 管理浏览器和树莓派的连接状态
- ✅ 维护会话生命周期（创建、连接、断开、清理）
- ✅ 线程安全的并发访问控制
- ✅ 自动超时清理机制

**关键类**：
- `VoiceSession`：单个语音会话的数据模型
- `VoiceSessionManager`：全局单例会话管理器
- `ClientType`：客户端类型枚举（浏览器/设备）
- `SessionStatus`：会话状态枚举

**行数**：~300 行

---

#### `app/services/websocket_handler.py`
**功能**：WebSocket 事件处理器
- ✅ 初始化 Flask-SocketIO
- ✅ 处理所有 WebSocket 事件（连接、断开、加入、音频数据）
- ✅ 音频数据双向转发
- ✅ 后台任务（定期清理超时会话）

**关键事件**：
- `connect` / `disconnect`：连接管理
- `browser_join` / `device_join`：加入会话
- `audio_data`：音频数据转发
- `ping` / `pong`：心跳
- `hangup`：挂断

**行数**：~250 行

---

#### `app/routes/voice.py`
**功能**：语音呼叫 REST API
- ✅ `/call/initiate`：发起语音呼叫
- ✅ `/call/terminate`：终止呼叫
- ✅ `/call/status/<id>`：查询会话状态
- ✅ `/sessions`：列出所有会话

**行数**：~150 行

---

### 2. 测试代码

#### `tests/test_websocket_client.py`
**功能**：WebSocket 自动化测试客户端
- ✅ 场景1：完整通话流程
- ✅ 场景2：单方连接超时
- ✅ 手动测试模式（浏览器/设备客户端）

**用法**：
```bash
python tests/test_websocket_client.py scenario1
python tests/test_websocket_client.py browser DEVICE_ID
python tests/test_websocket_client.py device DEVICE_ID
```

**行数**：~200 行

---

#### `tests/voice_test.http`
**功能**：REST API 测试（VSCode REST Client）
- ✅ 发起呼叫
- ✅ 查询状态
- ✅ 列出会话
- ✅ 终止呼叫

**行数**：~30 行

---

### 3. 文档

#### `docs/QUICKSTART.md`
**内容**：10分钟快速开始指南
- 安装依赖
- 配置环境
- 启动服务
- 快速测试
- 故障排查

**面向对象**：初次使用的开发者

---

#### `docs/WEBSOCKET_VOICE.md`
**内容**：WebSocket 语音功能完整文档
- 功能概述和工作流程
- 技术架构和特性
- REST API 接口文档
- WebSocket 事件协议
- 使用示例（浏览器 + 树莓派）
- 配置说明
- 测试方法
- 故障排查
- 部署建议

**面向对象**：需要集成功能的开发者

---

#### `docs/ARCHITECTURE.md`
**内容**：架构评审与设计文档
- 可行性评审总结
- 系统架构图
- 数据流时序图
- 核心组件设计
- 稳定性设计（超时、并发、异常、心跳）
- 性能优化建议
- 安全性建议
- 后续扩展方向

**面向对象**：架构师、技术负责人

---

#### `docs/ROADMAP.md`
**内容**：实施路线图
- ✅ 已完成：后端服务器
- 🚧 待实施：树莓派客户端
- 🚧 待实施：浏览器客户端
- 🚧 待实施：音频优化
- 完整时间规划
- 测试计划
- 部署清单
- 注意事项

**面向对象**：项目负责人、实施团队

---

## 🔄 已修改文件

### 1. `requirements.txt`
**新增依赖**：
```python
flask-socketio==5.3.6
python-socketio==5.11.1
gevent==24.2.1
gevent-websocket==0.10.1
```

---

### 2. `app/config.py`
**新增配置**：
```python
# WebSocket 配置
WS_CONNECTION_TIMEOUT: int = 30
WS_SESSION_TIMEOUT: int = 60
WS_HEARTBEAT_INTERVAL: int = 30
MAX_CONCURRENT_SESSIONS: int = 100
```

---

### 3. `app/__init__.py`
**修改内容**：
- 注册 `voice_bp` 蓝图
- 初始化 Flask-SocketIO
- 将 `socketio` 实例存储到 `app.socketio`

---

### 4. `main.py`
**修改内容**：
- 使用 `socketio.run()` 代替 `app.run()`
- 添加 WebSocket 启动日志

---

### 5. `README.md`
**修改内容**：
- 添加 WebSocket 语音功能说明
- 添加文档链接
- 更新快速开始指南

---

## 📊 代码统计

| 类型 | 文件数 | 代码行数（估算） |
|------|--------|------------------|
| **新增核心代码** | 3 | ~700 行 |
| **新增测试代码** | 2 | ~230 行 |
| **新增文档** | 5 | ~3000 行 |
| **修改现有文件** | 5 | ~50 行改动 |
| **总计** | 15 | ~4000 行 |

---

## 🎯 技术栈

### 后端
- **框架**：Flask + Flask-API
- **WebSocket**：Flask-SocketIO + python-socketio
- **异步引擎**：gevent
- **IoT通信**：华为云 IoTDA SDK
- **日志**：Python logging
- **配置**：python-dotenv

### 测试
- **REST 测试**：VSCode REST Client
- **WebSocket 测试**：python-socketio[client]

### 部署
- **容器化**：Docker + Docker Compose
- **反向代理**：Nginx（推荐）
- **进程管理**：systemd / supervisor

---

## 🔐 环境变量

### 现有配置
```bash
CLOUD_SDK_AK=xxx
CLOUD_SDK_SK=xxx
HUAWEI_PROJECT_ID=xxx
HUAWEI_REGION=cn-north-4
IOTDA_ENDPOINT=https://xxx.iotda-app.cn-north-4.myhuaweicloud.com
ZLM_SERVER=zlm-server
ZLM_RTMP_PORT=1935
PORT=5002
FLASK_DEBUG=false
LOG_FILE=logs/app.log
```

### 新增配置（可选）
```bash
WS_CONNECTION_TIMEOUT=30
WS_SESSION_TIMEOUT=60
WS_HEARTBEAT_INTERVAL=30
MAX_CONCURRENT_SESSIONS=100
```

---

## 📝 API 端点汇总

### 现有 API
- `GET  /vigidoor/health` - 健康检查
- `POST /vigidoor/api/v1/stream/start` - 开始推流
- `POST /vigidoor/api/v1/stream/stop` - 停止推流
- `POST /vigidoor/index/hook/on_stream_not_found` - ZLM Webhook
- `POST /vigidoor/index/hook/on_stream_none_reader` - ZLM Webhook

### 新增 API ✨
- `POST /vigidoor/api/v1/voice/call/initiate` - 发起语音呼叫
- `POST /vigidoor/api/v1/voice/call/terminate` - 终止呼叫
- `GET  /vigidoor/api/v1/voice/call/status/<id>` - 查询会话状态
- `GET  /vigidoor/api/v1/voice/sessions` - 列出所有会话

### WebSocket 端点 ✨
- `ws://server:5002` - Socket.IO WebSocket 连接

---

## 🚀 下一步

1. **立即可做**：
   - ✅ 安装依赖：`pip install -r requirements.txt`
   - ✅ 启动服务：`python main.py`
   - ✅ 运行测试：`python tests/test_websocket_client.py scenario1`

2. **后续开发**：
   - 🔴 树莓派 WebSocket 客户端集成
   - 🟡 浏览器 WebSocket 客户端集成
   - 🟢 音频处理优化

3. **参考文档**：
   - [快速开始](QUICKSTART.md)
   - [功能文档](WEBSOCKET_VOICE.md)
   - [实施路线图](ROADMAP.md)

---

**项目状态**：✅ **后端已完成，可立即开始客户端集成**

**版本**: 1.0  
**更新时间**: 2026-03-06
