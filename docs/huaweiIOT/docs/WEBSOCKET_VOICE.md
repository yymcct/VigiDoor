# WebSocket 语音中继功能文档

## 📖 功能概述

WebSocket 语音中继器实现了浏览器和树莓派设备之间的实时语音通信。

### 工作流程

```
浏览器 ←→ WebSocket ←→ Python中继服务器 ←→ WebSocket ←→ 树莓派
```

1. **发起呼叫**：用户在浏览器端按下呼叫按钮
2. **REST API**：浏览器调用 `/api/v1/voice/call/initiate` 接口
3. **通知设备**：服务器通过华为云 IoTDA (MQTT) 通知树莓派
4. **建立连接**：浏览器和树莓派都连接到 WebSocket
5. **音频转发**：服务器在双方之间转发音频数据
6. **结束通话**：任一方断开或主动挂断

---

## 🔧 技术架构

### 核心组件

| 组件 | 技术栈 | 说明 |
|------|--------|------|
| **会话管理器** | `voice_session.py` | 管理语音会话状态（线程安全） |
| **WebSocket处理器** | `websocket_handler.py` | 处理 Socket.IO 事件和消息转发 |
| **REST API** | `voice.py` | 提供语音呼叫控制接口 |
| **WebSocket引擎** | Flask-SocketIO + gevent | 异步 WebSocket 服务器 |

### 关键特性

✅ **按需连接**：不需要持久 WebSocket 连接，节省资源  
✅ **会话隔离**：每个设备独立会话，互不干扰  
✅ **超时管理**：自动清理超时会话  
✅ **线程安全**：会话管理器使用锁保护  
✅ **心跳机制**：保持连接活跃  
✅ **错误处理**：完善的异常处理和日志记录  

---

## 📡 API 接口文档

### 1. 发起语音呼叫

**请求**
```http
POST /api/v1/voice/call/initiate
Content-Type: application/json

{
  "device_id": "VIGIDOOR_xxx_RPI"
}
```

**响应**
```json
{
  "success": true,
  "session_id": "VIGIDOOR_xxx_RPI",
  "message": "语音呼叫已发起，请浏览器端连接 WebSocket",
  "device_notified": true,
  "iotda_msg_id": "uuid-xxx"
}
```

### 2. 查询会话状态

**请求**
```http
GET /api/v1/voice/call/status/{session_id}
```

**响应**
```json
{
  "success": true,
  "session_id": "VIGIDOOR_xxx_RPI",
  "device_id": "VIGIDOOR_xxx_RPI",
  "status": "connected",
  "browser_connected": true,
  "device_connected": true,
  "created_at": 1234567890.123,
  "connected_at": 1234567891.456,
  "browser_messages": 145,
  "device_messages": 138
}
```

### 3. 终止语音呼叫

**请求**
```http
POST /api/v1/voice/call/terminate
Content-Type: application/json

{
  "session_id": "VIGIDOOR_xxx_RPI"
}
```

**响应**
```json
{
  "success": true,
  "message": "会话 VIGIDOOR_xxx_RPI 已终止"
}
```

### 4. 列出所有会话（调试用）

**请求**
```http
GET /api/v1/voice/sessions
```

**响应**
```json
{
  "success": true,
  "total": 2,
  "sessions": [
    {
      "session_id": "VIGIDOOR_001_RPI",
      "device_id": "VIGIDOOR_001_RPI",
      "status": "connected",
      "browser_connected": true,
      "device_connected": true,
      "created_at": 1234567890.123,
      "browser_messages": 50,
      "device_messages": 48
    }
  ]
}
```

---

## 🔌 WebSocket 事件协议

### 连接建立

#### 浏览器端加入

```javascript
socket.emit('browser_join', {
  device_id: 'VIGIDOOR_xxx_RPI',
  session_id: 'VIGIDOOR_xxx_RPI'  // 可选，默认使用 device_id
});
```

#### 设备端加入

```javascript
socket.emit('device_join', {
  device_id: 'VIGIDOOR_xxx_RPI',
  session_id: 'VIGIDOOR_xxx_RPI'  // 可选
});
```

#### 加入成功响应

```javascript
socket.on('joined', (data) => {
  // data = {
  //   session_id: 'xxx',
  //   device_id: 'xxx',
  //   role: 'browser' | 'device',
  //   waiting_for_device: true/false
  // }
});
```

#### 通话建立通知

```javascript
socket.on('call_established', (data) => {
  // data = {
  //   message: '通话已建立',
  //   session_id: 'xxx'
  // }
});
```

### 音频数据传输

#### 发送音频

```javascript
socket.emit('audio_data', {
  audio: audioDataBlob,      // 音频数据（二进制或 base64）
  timestamp: Date.now(),     // 时间戳
  // 其他自定义字段...
});
```

#### 接收音频

```javascript
socket.on('audio_data', (data) => {
  const audioData = data.audio;
  const timestamp = data.timestamp;
  // 处理音频数据...
});
```

### 心跳保活

```javascript
// 发送心跳
socket.emit('ping');

// 接收心跳响应
socket.on('pong', () => {
  // 连接正常
});
```

### 挂断与断开

#### 主动挂断

```javascript
socket.emit('hangup');
```

#### 对方挂断通知

```javascript
socket.on('peer_hangup', (data) => {
  // data = { message: '对方已挂断' }
});
```

#### 对方断开通知

```javascript
socket.on('peer_disconnected', (data) => {
  // data = { message: '对方已断开连接' }
});
```

#### 服务器终止通知

```javascript
socket.on('call_terminated', (data) => {
  // data = { message: '服务器已终止通话' }
});
```

### 错误处理

```javascript
socket.on('error', (data) => {
  console.error('WebSocket 错误:', data.message);
});
```

---

## 🎯 使用示例

### 浏览器端示例

```html
<!DOCTYPE html>
<html>
<head>
  <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
</head>
<body>
  <button id="callBtn">发起呼叫</button>
  <button id="hangupBtn" disabled>挂断</button>
  
  <script>
    const deviceId = 'VIGIDOOR_001_RPI';
    let socket = null;
    
    // 发起呼叫
    document.getElementById('callBtn').onclick = async () => {
      // 1. 调用 REST API 发起呼叫
      const response = await fetch('http://localhost:5002/api/v1/voice/call/initiate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ device_id: deviceId })
      });
      
      const result = await response.json();
      
      if (result.success) {
        // 2. 连接 WebSocket
        socket = io('http://localhost:5002');
        
        socket.on('connect', () => {
          console.log('WebSocket 已连接');
          
          // 3. 加入会话
          socket.emit('browser_join', {
            device_id: deviceId,
            session_id: result.session_id
          });
        });
        
        socket.on('joined', (data) => {
          console.log('已加入会话:', data);
        });
        
        socket.on('call_established', (data) => {
          console.log('通话已建立:', data);
          document.getElementById('hangupBtn').disabled = false;
        });
        
        socket.on('audio_data', (data) => {
          // 处理接收到的音频数据
          console.log('收到音频数据:', data);
          playAudio(data.audio);
        });
        
        socket.on('peer_hangup', () => {
          console.log('对方已挂断');
          socket.disconnect();
        });
      }
    };
    
    // 挂断
    document.getElementById('hangupBtn').onclick = () => {
      if (socket) {
        socket.emit('hangup');
        socket.disconnect();
        socket = null;
        document.getElementById('hangupBtn').disabled = true;
      }
    };
    
    // 发送音频数据（示例）
    function sendAudio(audioBlob) {
      if (socket) {
        socket.emit('audio_data', {
          audio: audioBlob,
          timestamp: Date.now()
        });
      }
    }
    
    function playAudio(audioData) {
      // 实现音频播放逻辑
    }
  </script>
</body>
</html>
```

### 树莓派端示例 (Python)

```python
import socketio
import time

# 创建 Socket.IO 客户端
sio = socketio.Client()

device_id = "VIGIDOOR_001_RPI"
session_id = device_id

@sio.event
def connect():
    print("WebSocket 已连接")
    # 加入会话
    sio.emit('device_join', {
        'device_id': device_id,
        'session_id': session_id
    })

@sio.event
def joined(data):
    print(f"已加入会话: {data}")

@sio.event
def call_established(data):
    print(f"通话已建立: {data}")

@sio.event
def audio_data(data):
    # 处理接收到的音频数据
    print(f"收到音频数据")
    play_audio(data['audio'])

@sio.event
def peer_hangup(data):
    print("对方已挂断")
    sio.disconnect()

@sio.event
def disconnect():
    print("WebSocket 已断开")

# 连接到服务器
sio.connect('http://server-ip:5002')

# 发送音频数据
def send_audio(audio_data):
    sio.emit('audio_data', {
        'audio': audio_data,
        'timestamp': int(time.time() * 1000)
    })

def play_audio(audio_data):
    # 实现音频播放逻辑
    pass

# 保持连接
try:
    sio.wait()
except KeyboardInterrupt:
    sio.disconnect()
```

---

## ⚙️ 配置说明

### 环境变量

在 `.env` 文件中配置：

```bash
# WebSocket 配置
WS_CONNECTION_TIMEOUT=30      # WebSocket 连接超时（秒）
WS_SESSION_TIMEOUT=60         # 会话超时（秒）
WS_HEARTBEAT_INTERVAL=30      # 心跳间隔（秒）
MAX_CONCURRENT_SESSIONS=100   # 最大并发会话数
```

### 默认值

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `WS_CONNECTION_TIMEOUT` | 30秒 | 等待双方建立连接的最大时间 |
| `WS_SESSION_TIMEOUT` | 60秒 | 单方连接后等待另一方的最大时间 |
| `WS_HEARTBEAT_INTERVAL` | 30秒 | 心跳检测间隔 |
| `MAX_CONCURRENT_SESSIONS` | 100 | 允许的最大并发会话数 |

---

## 🧪 测试

### 安装测试依赖

```bash
pip install python-socketio[client]
```

### 运行测试

#### 1. 自动化测试场景

```bash
# 场景1：正常通话流程
python tests/test_websocket_client.py scenario1

# 场景2：单方连接超时测试
python tests/test_websocket_client.py scenario2
```

#### 2. 手动测试

**终端1 - 启动浏览器客户端：**
```bash
python tests/test_websocket_client.py browser VIGIDOOR_TEST_RPI
```

**终端2 - 启动设备客户端：**
```bash
python tests/test_websocket_client.py device VIGIDOOR_TEST_RPI
```

#### 3. REST API 测试

使用 VSCode REST Client 扩展打开 `tests/voice_test.http` 文件，逐个执行测试请求。

---

## 🔍 故障排查

### 常见问题

#### 1. WebSocket 连接失败

**症状**：浏览器或设备无法连接 WebSocket

**解决方案**：
- 检查服务器是否正常运行
- 确认防火墙是否开放端口 5002
- 检查 CORS 配置是否正确

#### 2. 设备未收到连接通知

**症状**：调用 `/call/initiate` 后设备没有响应

**解决方案**：
- 检查华为云 IoTDA 配置是否正确
- 确认设备已订阅 MQTT Topic: `vigidoor/down/{device_id}/command/stream`
- 查看服务器日志确认 IoTDA 消息是否发送成功

#### 3. 音频数据未转发

**症状**：一方发送音频，另一方收不到

**解决方案**：
- 检查双方是否都已连接（调用 `/call/status` API）
- 查看服务器日志确认消息转发情况
- 确认 `audio_data` 事件名称正确

#### 4. 会话超时被清理

**症状**：会话自动关闭

**解决方案**：
- 增大 `WS_SESSION_TIMEOUT` 配置
- 确保双方在超时时间内都连接
- 实现心跳机制保持连接

### 查看日志

```bash
# 实时查看日志
tail -f logs/app.log

# 搜索特定会话
grep "VIGIDOOR_xxx_RPI" logs/app.log

# 查看错误日志
grep "ERROR" logs/app.log
```

---

## 🚀 部署建议

### 生产环境配置

1. **使用 Nginx 反向代理**

```nginx
upstream websocket_backend {
    server 127.0.0.1:5002;
}

server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://websocket_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        
        # WebSocket 超时配置
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
```

2. **使用 HTTPS**

```bash
# 使用 Let's Encrypt 获取 SSL 证书
certbot --nginx -d your-domain.com
```

3. **配置 CORS**

在 `websocket_handler.py` 中修改：

```python
socketio = SocketIO(
    app,
    cors_allowed_origins=["https://your-frontend-domain.com"],
    async_mode='gevent',
    # ...
)
```

4. **监控和日志**

- 使用 `supervisord` 或 `systemd` 管理进程
- 配置日志轮转
- 设置性能监控告警

---

## 📊 性能指标

### 资源消耗（参考）

| 指标 | 单会话 | 100并发会话 |
|------|--------|-------------|
| 内存 | ~5 MB | ~200 MB |
| CPU | <1% | ~10% |
| 网络 | 取决于音频码率 | - |

### 扩展性

- **垂直扩展**：增加服务器 CPU/内存
- **水平扩展**：使用 Redis 作为消息队列，部署多个实例
- **负载均衡**：Nginx 或 HAProxy

---

## 📝 开发注意事项

1. **音频格式**：浏览器和树莓派需要协商统一的音频编码格式（如 Opus、PCM）
2. **数据大小**：注意单次传输的音频数据不要过大，建议分片传输
3. **缓冲策略**：实现音频缓冲机制，平滑网络抖动
4. **错误重连**：客户端实现断线重连逻辑
5. **安全性**：生产环境建议添加身份认证和加密

---

## 📚 参考资料

- [Flask-SocketIO 文档](https://flask-socketio.readthedocs.io/)
- [Socket.IO 客户端文档](https://socket.io/docs/v4/client-api/)
- [华为云 IoTDA 文档](https://support.huaweicloud.com/api-iothub/iot_06_v5_0001.html)

---

**版本**: 1.0  
**更新时间**: 2026-03-06
