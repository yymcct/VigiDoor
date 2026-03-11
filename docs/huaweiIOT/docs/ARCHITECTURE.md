# WebSocket 语音中继架构设计

## 架构评审总结

### ✅ 方案可行性：可行且推荐

### 优势分析

1. **资源高效**
   - 按需连接，避免持久连接的资源浪费
   - 支持动态扩展，可承载大量设备

2. **架构清晰**
   - 职责分离：MQTT用于控制，WebSocket用于数据传输
   - 中继模式便于统一管理、监控和日志记录
   - 与现有Flask架构无缝集成

3. **扩展性强**
   - 支持一对一、一对多等多种场景
   - 可轻松添加录音、转码等功能
   - 便于后续增加视频通话功能

4. **稳定性保障**
   - 完善的超时处理机制
   - 自动会话清理
   - 线程安全的会话管理
   - 心跳保活机制

---

## 系统架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                         智慧安防门系统                                │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────┐                                        ┌──────────────┐
│   浏览器端    │                                        │   树莓派端    │
│  (Web App)  │                                        │  (RPI + CAM) │
└──────┬───────┘                                        └──────┬───────┘
       │                                                       │
       │ ① HTTP POST                                          │
       │ /vigidoor/api/v1/voice/call/initiate                          │
       │                                                       │
       ▼                                                       │
┌─────────────────────────────────────────────────────┐       │
│           Python Flask 服务器 (5002)                  │       │
│  ┌─────────────────────────────────────────────┐   │       │
│  │         REST API 层                          │   │       │
│  │  - 推流控制 (stream.py)                      │   │       │
│  │  - 语音呼叫 (voice.py)  ← NEW               │   │       │
│  │  - 健康检查 (health.py)                      │   │       │
│  └─────────────┬───────────────────────────────┘   │       │
│                │                                     │       │
│                ▼                                     │       │
│  ┌─────────────────────────────────────────────┐   │       │
│  │         服务层                               │   │       │
│  │  - 会话管理 (voice_session.py)  ← NEW       │   │       │
│  │  - IoTDA 客户端 (iotda.py)                   │   │       │
│  └─────────────┬───────────────────────────────┘   │       │
│                │                                     │       │
│                │ ② MQTT 下发连接通知                  │       │
│                ▼                                     │       │
│  ┌─────────────────────────────────────────────┐   │       │
│  │    WebSocket 处理层 (Flask-SocketIO)         │   │       │
│  │  - 事件路由 (websocket_handler.py) ← NEW    │   │       │
│  │  - 音频数据转发                              │   │       │
│  │  - 连接管理                                  │   │       │
│  └─────────────┬───────────────────────────────┘   │       │
└────────────────┼───────────────────────────────────┘       │
                 │                                             │
                 │ ③ WebSocket 连接                            │
                 │    (Socket.IO)                              │
                 │                                             │
                 │◄────────────④ MQTT 通知到达 ────────────────┤
                 │                                             │
                 │◄────────────⑤ WebSocket 连接 ───────────────┤
                 │                                             │
                 │───────────⑥ 双向音频数据流 ─────────────────►│
                 │                                             │

┌─────────────────────────────────────────────────────────────────────┐
│                      华为云 IoTDA 平台                                │
│                     (MQTT Broker)                                    │
│  Topic: vigidoor/down/{device_id}/command/stream                    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 数据流时序图

```
浏览器               Flask服务器              华为云IoTDA           树莓派
  │                      │                      │                 │
  │  ① POST /call/       │                      │                 │
  │     initiate         │                      │                 │
  ├─────────────────────►│                      │                 │
  │                      │                      │                 │
  │  ② 返回session_id    │                      │                 │
  │◄─────────────────────┤                      │                 │
  │                      │                      │                 │
  │                      │  ③ MQTT 下发连接通知  │                 │
  │                      ├─────────────────────►│                 │
  │                      │                      │  ④ MQTT推送      │
  │                      │                      ├────────────────►│
  │                      │                      │                 │
  │  ⑤ WebSocket 连接    │                      │                 │
  ├─────────────────────►│                      │                 │
  │  emit('browser_join')│                      │                 │
  │                      │                      │                 │
  │                      │                      │  ⑥ WebSocket连接 │
  │                      │◄─────────────────────┼─────────────────┤
  │                      │        emit('device_join')             │
  │                      │                      │                 │
  │  ⑦ 'joined' 事件     │                      │                 │
  │◄─────────────────────┤                      │                 │
  │                      │                      │  'joined' 事件   │
  │                      ├──────────────────────┼────────────────►│
  │                      │                      │                 │
  │  ⑧ 'call_established'│                      │                 │
  │◄─────────────────────┤                      │                 │
  │                      │                      │ 'call_established'│
  │                      ├──────────────────────┼────────────────►│
  │                      │                      │                 │
  │                      │   ⑨ 通话阶段（音频数据双向传输）         │
  │  emit('audio_data')  │                      │                 │
  ├─────────────────────►│                      │                 │
  │                      │  转发 'audio_data'    │                 │
  │                      ├──────────────────────┼────────────────►│
  │                      │                      │                 │
  │                      │                      │ emit('audio_data')│
  │  转发 'audio_data'   │◄─────────────────────┼─────────────────┤
  │◄─────────────────────┤                      │                 │
  │                      │                      │                 │
  │  ⑩ emit('hangup')    │                      │                 │
  ├─────────────────────►│                      │                 │
  │                      │                      │ 'peer_hangup'    │
  │                      ├──────────────────────┼────────────────►│
  │                      │                      │                 │
  │  disconnect          │                      │  disconnect      │
  ├─────────────────────►│◄─────────────────────┼─────────────────┤
  │                      │                      │                 │
  │                      │  ⑪ 清理会话           │                 │
  │                      │                      │                 │
```

---

## 核心组件设计

### 1. 会话管理器 (VoiceSessionManager)

**职责**：
- 创建和管理语音会话
- 维护会话状态（等待、已连接、断开中、已关闭）
- 管理浏览器和设备的 SID 映射
- 线程安全的并发访问控制
- 自动清理超时会话

**关键数据结构**：
```python
@dataclass
class VoiceSession:
    session_id: str           # 会话ID（通常使用device_id）
    device_id: str            # 设备ID
    status: SessionStatus     # 会话状态
    browser_sid: str          # 浏览器 SocketIO SID
    device_sid: str           # 设备 SocketIO SID
    created_at: float         # 创建时间
    connected_at: float       # 双方连接时间
    browser_messages: int     # 浏览器消息计数
    device_messages: int      # 设备消息计数
```

**线程安全**：
- 单例模式 + 双重检查锁
- 所有修改操作使用 RLock 保护

---

### 2. WebSocket 事件处理器 (websocket_handler.py)

**核心事件**：

| 事件 | 方向 | 说明 |
|------|------|------|
| `connect` | Client → Server | 客户端连接 |
| `disconnect` | Client → Server | 客户端断开 |
| `browser_join` | Browser → Server | 浏览器加入会话 |
| `device_join` | Device → Server | 设备加入会话 |
| `joined` | Server → Client | 加入成功通知 |
| `call_established` | Server → Both | 通话建立通知 |
| `audio_data` | Both ↔ Server ↔ Both | 音频数据双向传输 |
| `ping` / `pong` | Client ↔ Server | 心跳检测 |
| `hangup` | Client → Server | 主动挂断 |
| `peer_hangup` | Server → Peer | 对方挂断通知 |
| `peer_disconnected` | Server → Peer | 对方断开通知 |

**消息转发逻辑**：
```python
# 简化流程
1. 接收 audio_data 事件
2. 从会话管理器查找发送方所属会话
3. 判断发送方类型（浏览器 or 设备）
4. 获取对端的 SID
5. 转发数据到对端
```

---

### 3. REST API 层 (voice.py)

**接口设计**：

| 接口 | 方法 | 功能 | 调用者 |
|------|------|------|--------|
| `/call/initiate` | POST | 发起语音呼叫 | 浏览器 |
| `/call/terminate` | POST | 终止语音呼叫 | 浏览器/后台 |
| `/call/status/{id}` | GET | 查询会话状态 | 浏览器/监控 |
| `/sessions` | GET | 列出所有会话 | 调试/监控 |

---

## 稳定性设计

### 1. 超时处理

**场景**：
- ✅ 浏览器连接后，设备长时间未连接
- ✅ 设备连接后，浏览器长时间未连接
- ✅ 网络异常导致静默断开

**解决方案**：
```python
# 后台定时任务，每30秒检查一次
def cleanup_expired_sessions_task():
    while True:
        time.sleep(30)
        session_manager.cleanup_expired_sessions(
            timeout=Config.WS_SESSION_TIMEOUT
        )
```

**超时策略**：
- 单方连接超时：`WS_SESSION_TIMEOUT` (默认60秒)
- 双方已连接：依赖心跳机制，由 SocketIO 自动处理

---

### 2. 并发控制

**限制并发会话数**：
```python
if session_manager.get_active_sessions_count() >= Config.MAX_CONCURRENT_SESSIONS:
    return error("已达到最大并发会话数")
```

**防止重复连接**：
```python
# 同一设备的浏览器端或设备端，只允许一个连接
if session.browser_sid is not None:
    return error("该会话的浏览器端已连接")
```

---

### 3. 异常处理

**分层异常处理**：
1. **WebSocket 事件层**：捕获所有异常，记录日志，发送 `error` 事件
2. **REST API 层**：返回标准错误响应 `{"success": false, "error": "..."}`
3. **服务层**：抛出具体异常，由上层处理

**日志记录**：
- INFO：正常流程（连接、断开、消息转发）
- WARNING：异常情况（超时、重复连接）
- ERROR：严重错误（IoTDA 通知失败、会话管理异常）

---

### 4. 心跳机制

**SocketIO 内置心跳**：
- `ping_interval`: 25秒
- `ping_timeout`: 60秒

**应用层心跳**（可选）：
```javascript
// 客户端定期发送心跳
setInterval(() => {
  socket.emit('ping');
}, 30000);

socket.on('pong', () => {
  // 连接正常
});
```

---

## 性能优化建议

### 1. 音频数据优化

**建议**：
- 使用 Opus 编码（低延迟、高压缩率）
- 数据分片传输（每片 20-60ms 音频）
- 避免传输原始 PCM 数据

**示例**：
```javascript
// 浏览器端使用 MediaRecorder API
const mediaRecorder = new MediaRecorder(stream, {
  mimeType: 'audio/webm;codecs=opus',
  audioBitsPerSecond: 16000  // 16kbps
});

mediaRecorder.ondataavailable = (event) => {
  socket.emit('audio_data', {
    audio: event.data,
    timestamp: Date.now()
  });
};
```

---

### 2. 负载均衡（后续扩展）

**水平扩展方案**：
```
浏览器 ──┐
         ├──► Nginx ──┬──► Flask实例1 ──┐
设备端 ──┘            │                  ├──► Redis (消息队列)
                      ├──► Flask实例2 ──┤
                      └──► Flask实例3 ──┘
```

**注意事项**：
- 需要使用 Redis 作为 SocketIO 消息队列
- 配置 `socketio = SocketIO(app, message_queue='redis://...')`
- 保证会话亲和性（同一会话的双方连接到同一实例）

---

### 3. 监控与告警

**关键指标**：
- 活跃会话数
- 平均会话时长
- 音频消息吞吐量
- 超时会话数
- WebSocket 连接/断开频率

**监控方案**：
- Prometheus + Grafana
- 自定义 `/metrics` 端点

---

## 安全性建议

### 1. 身份认证

**方案**：
```python
# WebSocket 连接时验证 token
@sio.on('connect')
def handle_connect():
    token = request.args.get('token')
    if not verify_token(token):
        return False  # 拒绝连接
```

---

### 2. 数据加密

**建议**：
- 生产环境必须使用 HTTPS/WSS
- 端到端加密音频数据（可选）

---

### 3. CORS 配置

**生产环境**：
```python
socketio = SocketIO(
    app,
    cors_allowed_origins=[
        "https://your-frontend-domain.com"
    ]
)
```

---

## 后续扩展方向

### 1. 功能扩展

- ✨ 录音功能（保存通话记录）
- ✨ 多人会议（一对多喊话）
- ✨ 视频通话支持
- ✨ 文字消息（辅助语音）
- ✨ 文件传输

---

### 2. 技术优化

- 🔧 音频缓冲与抗抖动
- 🔧 自适应码率调整
- 🔧 WebRTC 集成（P2P模式）
- 🔧 AI 降噪与语音增强

---

## 结论

该架构设计：
- ✅ **可行性高**：技术成熟，实现简单
- ✅ **扩展性强**：易于添加新功能
- ✅ **稳定性好**：完善的异常处理和超时机制
- ✅ **维护性强**：代码结构清晰，职责分离

**推荐实施，可直接用于生产环境！**


