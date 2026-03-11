# WebSocket 语音中继 - 实施路线图

本文档为你提供完整的实施路线图，帮助你从现在的后端实现到最终的端到端语音通话系统。

---

## ✅ 已完成（后端服务器）

### 1. WebSocket 中继服务器 ✓

**已实现的功能**：
- ✅ Flask-SocketIO 集成
- ✅ 会话管理系统（线程安全）
- ✅ WebSocket 事件处理（连接、断开、音频转发）
- ✅ REST API（发起呼叫、查询状态、终止呼叫）
- ✅ 超时管理和自动清理
- ✅ 心跳机制
- ✅ 完整的日志和错误处理

**文件清单**：
```
app/
  routes/
    voice.py                 # 语音呼叫 REST API
  services/
    voice_session.py         # 会话管理器
    websocket_handler.py     # WebSocket 事件处理
  config.py                  # WebSocket 配置项
tests/
  test_websocket_client.py   # Python 测试客户端
  voice_test.http            # REST API 测试
docs/
  WEBSOCKET_VOICE.md         # 完整功能文档
  ARCHITECTURE.md            # 架构设计文档
  QUICKSTART.md              # 快速开始指南
```

**测试状态**：
- ✅ 自动化测试通过
- ✅ REST API 可用
- ✅ WebSocket 连接稳定
- ✅ 音频数据转发正常

---

## 🚧 待实施（客户端）

### 阶段1：树莓派端集成 🔴

**目标**：树莓派收到 MQTT 通知后，能够连接 WebSocket 并进行音频通信。

#### 1.1 更新 MQTT 订阅

**文件**：树莓派端的 MQTT 客户端

**修改**：订阅新的命令类型

```python
# 订阅 Topic
topic = f"vigidoor/down/{device_id}/command/stream"

# 处理消息
def on_message(client, userdata, msg):
    payload = json.loads(msg.payload)
    action = payload['data']['action']
    
    if action == "connect_websocket":
        # 新增：连接 WebSocket
        session_id = payload['data']['session_id']
        connect_to_websocket(session_id)
    
    elif action == "start":
        # 现有：开始推流
        start_rtmp_stream(payload['data'])
    
    elif action == "stop":
        # 现有：停止推流
        stop_rtmp_stream()
```

#### 1.2 实现 WebSocket 客户端

**依赖**：
```bash
pip install python-socketio[client]
```

**示例代码**（Python）：

```python
import socketio
import pyaudio
import time

class VoiceClient:
    def __init__(self, server_url, device_id):
        self.server_url = server_url
        self.device_id = device_id
        self.sio = socketio.Client()
        self.audio = pyaudio.PyAudio()
        self.stream = None
        
        self._register_events()
    
    def _register_events(self):
        @self.sio.event
        def connect():
            print("WebSocket 已连接")
            # 加入会话
            self.sio.emit('device_join', {
                'device_id': self.device_id,
                'session_id': self.device_id
            })
        
        @self.sio.event
        def joined(data):
            print(f"已加入会话: {data}")
        
        @self.sio.event
        def call_established(data):
            print(f"通话已建立: {data}")
            # 开始音频采集
            self.start_audio_capture()
        
        @self.sio.event
        def audio_data(data):
            # 播放接收到的音频
            self.play_audio(data['audio'])
        
        @self.sio.event
        def peer_hangup(data):
            print("对方已挂断")
            self.stop_audio_capture()
            self.sio.disconnect()
    
    def connect(self):
        self.sio.connect(self.server_url)
    
    def start_audio_capture(self):
        # 配置音频参数
        CHUNK = 1024
        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = 16000
        
        self.stream = self.audio.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            output=True,
            frames_per_buffer=CHUNK
        )
        
        # 开启音频发送线程
        import threading
        threading.Thread(target=self._send_audio_loop, daemon=True).start()
    
    def _send_audio_loop(self):
        while self.stream and self.stream.is_active():
            try:
                audio_data = self.stream.read(1024)
                self.sio.emit('audio_data', {
                    'audio': audio_data,
                    'timestamp': int(time.time() * 1000)
                })
            except Exception as e:
                print(f"音频采集错误: {e}")
    
    def play_audio(self, audio_data):
        if self.stream:
            self.stream.write(audio_data)
    
    def stop_audio_capture(self):
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None

# 使用示例
def connect_to_websocket(session_id):
    client = VoiceClient(
        server_url="http://your-server:5002",
        device_id=session_id
    )
    client.connect()
```

**预计工作量**：1-2天

---

### 阶段2：浏览器端集成 🟡

**目标**：用户在 Web 界面上点击按钮，发起语音呼叫并进行实时通话。

#### 2.1 添加 Socket.IO 客户端库

**HTML**：
```html
<script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
```

或使用 npm：
```bash
npm install socket.io-client
```

#### 2.2 实现呼叫界面

**示例代码**（JavaScript/React）：

```javascript
import io from 'socket.io-client';

class VoiceCallManager {
  constructor(serverUrl, deviceId) {
    this.serverUrl = serverUrl;
    this.deviceId = deviceId;
    this.socket = null;
    this.mediaStream = null;
    this.audioContext = null;
  }
  
  async initiateCall() {
    // 1. 调用 REST API 发起呼叫
    const response = await fetch(`${this.serverUrl}/vigidoor/api/v1/voice/call/initiate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ device_id: this.deviceId })
    });
    
    const result = await response.json();
    
    if (!result.success) {
      throw new Error(result.error);
    }
    
    // 2. 连接 WebSocket
    this.socket = io(this.serverUrl);
    
    this.socket.on('connect', () => {
      console.log('WebSocket 已连接');
      
      // 3. 加入会话
      this.socket.emit('browser_join', {
        device_id: this.deviceId,
        session_id: result.session_id
      });
    });
    
    this.socket.on('call_established', async () => {
      console.log('通话已建立');
      // 开始音频采集
      await this.startAudioCapture();
    });
    
    this.socket.on('audio_data', (data) => {
      // 播放接收到的音频
      this.playAudio(data.audio);
    });
    
    this.socket.on('peer_hangup', () => {
      this.endCall();
    });
  }
  
  async startAudioCapture() {
    // 获取麦克风权限
    this.mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        sampleRate: 16000
      }
    });
    
    // 使用 MediaRecorder 或 Web Audio API 采集音频
    this.audioContext = new AudioContext({ sampleRate: 16000 });
    const source = this.audioContext.createMediaStreamSource(this.mediaStream);
    
    // 使用 ScriptProcessorNode 或 AudioWorklet 处理音频
    const processor = this.audioContext.createScriptProcessor(4096, 1, 1);
    
    processor.onaudioprocess = (e) => {
      const inputData = e.inputBuffer.getChannelData(0);
      
      // 将 Float32Array 转换为 Int16Array
      const int16Data = this.float32ToInt16(inputData);
      
      // 发送到服务器
      this.socket.emit('audio_data', {
        audio: int16Data,
        timestamp: Date.now()
      });
    };
    
    source.connect(processor);
    processor.connect(this.audioContext.destination);
  }
  
  playAudio(audioData) {
    // 实现音频播放
    // 使用 Web Audio API 或 <audio> 元素
  }
  
  float32ToInt16(float32Array) {
    const int16Array = new Int16Array(float32Array.length);
    for (let i = 0; i < float32Array.length; i++) {
      const s = Math.max(-1, Math.min(1, float32Array[i]));
      int16Array[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }
    return int16Array;
  }
  
  endCall() {
    if (this.socket) {
      this.socket.emit('hangup');
      this.socket.disconnect();
      this.socket = null;
    }
    
    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach(track => track.stop());
      this.mediaStream = null;
    }
    
    if (this.audioContext) {
      this.audioContext.close();
      this.audioContext = null;
    }
  }
}

// 使用示例
const voiceCall = new VoiceCallManager('http://localhost:5002', 'VIGIDOOR_001_RPI');

// 发起呼叫
document.getElementById('callBtn').onclick = () => {
  voiceCall.initiateCall();
};

// 挂断
document.getElementById('hangupBtn').onclick = () => {
  voiceCall.endCall();
};
```

**预计工作量**：2-3天

---

### 阶段3：音频处理优化 🟢

**目标**：提升音频质量和通话体验。

#### 3.1 音频编解码

**推荐使用 Opus 编码**：
- 浏览器：使用 MediaRecorder API（自动 Opus 编码）
- 树莓派：使用 OpusEncoder/OpusDecoder

**npm 包**：
```bash
npm install opus-encoder
```

**Python 包**：
```bash
pip install opuslib
```

#### 3.2 音频缓冲

**目的**：平滑网络抖动，避免爆音

```javascript
// 浏览器端缓冲器
class AudioBuffer {
  constructor(bufferSize = 10) {
    this.buffer = [];
    this.bufferSize = bufferSize;
  }
  
  push(audioData) {
    this.buffer.push(audioData);
    if (this.buffer.length > this.bufferSize) {
      this.buffer.shift();
    }
  }
  
  pop() {
    return this.buffer.shift();
  }
  
  isEmpty() {
    return this.buffer.length === 0;
  }
}
```

#### 3.3 回声消除

- 浏览器：使用 `echoCancellation: true`（已在示例中）
- 树莓派：使用 `webrtcvad` 或硬件 AEC

**预计工作量**：3-5天

---

## 📅 完整时间规划

| 阶段 | 任务 | 预计时间 | 优先级 |
|------|------|----------|--------|
| ✅ 后端 | WebSocket 服务器实现 | 已完成 | P0 |
| 🔴 阶段1 | 树莓派 WebSocket 客户端 | 1-2天 | P0 |
| 🟡 阶段2 | 浏览器 WebSocket 客户端 | 2-3天 | P0 |
| 🟢 阶段3 | 音频处理优化 | 3-5天 | P1 |
| ⚪ 后续 | 视频通话支持 | 待定 | P2 |
| ⚪ 后续 | 录音功能 | 待定 | P2 |

**总计**：核心功能预计 6-10 个工作日

---

## 🧪 测试计划

### 1. 单元测试
- [x] 后端会话管理
- [x] 后端 WebSocket 事件
- [ ] 树莓派音频采集
- [ ] 浏览器音频采集

### 2. 集成测试
- [x] 后端自动化测试（scenario1/scenario2）
- [ ] 浏览器 ↔ 后端
- [ ] 树莓派 ↔ 后端
- [ ] 浏览器 ↔ 后端 ↔ 树莓派（端到端）

### 3. 性能测试
- [ ] 并发会话压力测试（目标：100并发）
- [ ] 音频延迟测试（目标：<500ms）
- [ ] 长时间通话稳定性（目标：>30分钟）

### 4. 兼容性测试
- [ ] 浏览器兼容（Chrome, Firefox, Safari, Edge）
- [ ] 网络环境（WiFi, 4G, 弱网）
- [ ] 树莓派硬件（不同型号）

---

## 🚀 部署清单

### 开发环境
- [x] 本地 Flask 服务器运行
- [ ] 树莓派开发环境搭建
- [ ] 浏览器开发调试

### 测试环境
- [ ] Docker 容器部署
- [ ] 内网测试
- [ ] 模拟弱网环境

### 生产环境
- [ ] HTTPS/WSS 配置
- [ ] Nginx 反向代理
- [ ] 负载均衡（可选）
- [ ] 监控告警
- [ ] 日志收集

---

## 📝 注意事项

### 1. 音频格式协商
确保浏览器和树莓派使用相同的音频格式：
- **采样率**：16000 Hz（推荐）
- **通道数**：单声道（Mono）
- **编码**：Opus 或 PCM
- **位深**：16-bit

### 2. 网络要求
- **带宽**：最低 50 Kbps（双向）
- **延迟**：建议 <200ms
- **丢包率**：建议 <5%

### 3. 安全性
- 生产环境必须使用 HTTPS/WSS
- 建议添加 Token 认证
- 限制 CORS 来源

### 4. 用户体验
- 添加呼叫中状态指示
- 实现断线重连
- 提供音频质量反馈
- 添加麦克风/扬声器权限引导

---

## 🆘 遇到问题？

1. **查看文档**：
   - [快速开始指南](QUICKSTART.md)
   - [WebSocket 功能文档](WEBSOCKET_VOICE.md)
   - [架构设计文档](ARCHITECTURE.md)

2. **查看日志**：
   ```bash
   tail -f logs/app.log
   ```

3. **运行测试**：
   ```bash
   python tests/test_websocket_client.py scenario1
   ```

4. **调试工具**：
   - 浏览器开发者工具（Network, Console）
   - Wireshark（抓包分析）
   - Postman/REST Client（API 测试）

---

## 🎯 成功标准

最终系统应实现：

✅ 用户在浏览器点击"呼叫"按钮  
✅ 服务器通过 MQTT 通知树莓派  
✅ 树莓派连接 WebSocket  
✅ 浏览器连接 WebSocket  
✅ 双方建立语音通话  
✅ 实时双向音频传输  
✅ 挂断后正常断开  
✅ 异常情况自动恢复  

---

**祝你实施顺利！** 🎉

如有疑问，请随时查阅文档或联系技术支持。
