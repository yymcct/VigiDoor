# 快速开始指南

本指南帮助你快速部署和测试 WebSocket 语音中继功能。

---

## 📦 安装依赖

### 1. 更新 Python 依赖

```bash
cd /home/ubuntu/VigiDoor/docs/huaweiIOT
pip install -r requirements.txt
```

新增的依赖包：
- `flask-socketio==5.3.6` - Flask WebSocket 支持
- `python-socketio==5.11.1` - Socket.IO 核心库
- `gevent==24.2.1` - 异步事件循环
- `gevent-websocket==0.10.1` - WebSocket 支持

### 2. 配置环境变量

编辑 `.env` 文件（如果不存在则创建）：

```bash
# 华为云 IoTDA 配置（必填）
CLOUD_SDK_AK=your_access_key
CLOUD_SDK_SK=your_secret_key
HUAWEI_PROJECT_ID=your_project_id
HUAWEI_REGION=cn-north-4
IOTDA_ENDPOINT=https://xxxxx.iotda-app.cn-north-4.myhuaweicloud.com

# WebSocket 配置（可选，使用默认值）
WS_CONNECTION_TIMEOUT=30
WS_SESSION_TIMEOUT=60
WS_HEARTBEAT_INTERVAL=30
MAX_CONCURRENT_SESSIONS=100

# 服务配置
PORT=5002
FLASK_DEBUG=false
LOG_FILE=logs/app.log
```

---

## 🚀 启动服务

### 方法1：直接运行

```bash
python main.py
```

你应该看到类似输出：

```
2026-03-06 10:00:00 [INFO] __main__ - === 推流控制服务启动 ===
2026-03-06 10:00:00 [INFO] __main__ - IoTDA Endpoint : https://xxxxx.iotda-app.cn-north-4.myhuaweicloud.com
2026-03-06 10:00:00 [INFO] __main__ - Region         : cn-north-4
2026-03-06 10:00:00 [INFO] __main__ - Project ID     : your_project_id
2026-03-06 10:00:00 [INFO] __main__ - ZLM Server     : zlm-server:1935
2026-03-06 10:00:00 [INFO] __main__ - Listen Port    : 5002
2026-03-06 10:00:00 [INFO] __main__ - WebSocket      : 已启用（Socket.IO）
2026-03-06 10:00:00 [INFO] app.services.iotda - IoTDA 客户端初始化成功
2026-03-06 10:00:00 [INFO] app.services.voice_session - VoiceSessionManager 初始化
2026-03-06 10:00:00 [INFO] app.services.websocket_handler - SocketIO 初始化完成
2026-03-06 10:00:00 [INFO] __main__ - IoTDA 客户端初始化成功，服务就绪
```

### 方法2：使用 Docker（推荐生产环境）

```bash
# 构建镜像
docker build -t vigidoor-server .

# 运行容器
docker run -d \
  --name vigidoor-server \
  -p 5002:5002 \
  --env-file .env \
  vigidoor-server
```

### 方法3：使用 Docker Compose

```bash
docker-compose up -d
```

---

## ✅ 验证安装

### 1. 健康检查

```bash
curl http://localhost:5002/health
```

预期响应：
```json
{
  "status": "healthy",
  "timestamp": "2026-03-06T10:00:00.000000"
}
```

### 2. 查看会话列表

```bash
curl http://localhost:5002/api/v1/voice/sessions
```

预期响应（初始为空）：
```json
{
  "success": true,
  "total": 0,
  "sessions": []
}
```

---

## 🧪 快速测试

### 场景1：自动化集成测试

运行内置的自动化测试脚本：

```bash
# 安装测试客户端依赖
pip install python-socketio[client]

# 运行测试场景1（完整通话流程）
python tests/test_websocket_client.py scenario1
```

你应该看到：
```
========== 测试场景1：正常通话流程 ==========

[INFO] 步骤1: 浏览器连接...
[INFO] [browser] 正在连接到 http://localhost:5002...
[INFO] [browser] 已连接到服务器
[INFO] [browser] 服务器就绪: {'message': '服务器已就绪'}
[INFO] [browser] 已加入会话: {...}

[INFO] 步骤2: 设备连接...
[INFO] [device] 正在连接到 http://localhost:5002...
[INFO] [device] 已连接到服务器
[INFO] [device] 服务器就绪: {'message': '服务器已就绪'}
[INFO] [device] 已加入会话: {...}
[INFO] [browser] 通话已建立: {'message': '通话已建立', 'session_id': 'VIGIDOOR_TEST_RPI'}
[INFO] [device] 通话已建立: {'message': '通话已建立', 'session_id': 'VIGIDOOR_TEST_RPI'}

[INFO] 步骤3: 浏览器发送音频...
[INFO] [browser] 已发送音频数据: 26 bytes
[INFO] [device] 收到音频数据: 90 bytes

[INFO] 步骤4: 设备发送音频...
[INFO] [device] 已发送音频数据: 26 bytes
[INFO] [browser] 收到音频数据: 90 bytes

[INFO] 步骤5: 心跳测试...

[INFO] 步骤6: 浏览器挂断...
[INFO] [browser] 挂断通话
[INFO] [device] 对方已挂断: {'message': '对方已挂断'}

✅ 测试场景1 完成
```

---

### 场景2：手动测试

#### 步骤1：启动测试客户端

**终端1 - 浏览器端**：
```bash
python tests/test_websocket_client.py browser VIGIDOOR_001_RPI
```

**终端2 - 设备端**：
```bash
python tests/test_websocket_client.py device VIGIDOOR_001_RPI
```

#### 步骤2：观察日志

两个终端都应显示：
```
[INFO] [browser/device] 已连接到服务器
[INFO] [browser/device] 已加入会话
[INFO] [browser/device] 通话已建立
```

#### 步骤3：查看服务器日志

```bash
tail -f logs/app.log
```

应该看到：
```
[INFO] 客户端连接: SID=xxxxxxxx...
[INFO] 浏览器加入会话: device_id=VIGIDOOR_001_RPI
[INFO] 客户端 browser (SID: xxxxxxxx...) 已连接到会话 VIGIDOOR_001_RPI
[INFO] 设备加入会话: device_id=VIGIDOOR_001_RPI
[INFO] 客户端 device (SID: yyyyyyyy...) 已连接到会话 VIGIDOOR_001_RPI
```

---

### 场景3：REST API 测试

使用 VSCode REST Client 或 curl 测试：

```bash
# 1. 发起呼叫
curl -X POST http://localhost:5002/api/v1/voice/call/initiate \
  -H "Content-Type: application/json" \
  -d '{"device_id": "VIGIDOOR_002_RPI"}'

# 2. 查询会话状态
curl http://localhost:5002/api/v1/voice/call/status/VIGIDOOR_002_RPI

# 3. 列出所有会话
curl http://localhost:5002/api/v1/voice/sessions

# 4. 终止呼叫
curl -X POST http://localhost:5002/api/v1/voice/call/terminate \
  -H "Content-Type: application/json" \
  -d '{"session_id": "VIGIDOOR_002_RPI"}'
```

---

## 🌐 浏览器集成示例

### 最简浏览器客户端

创建 `test.html`：

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>WebSocket 语音测试</title>
  <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
</head>
<body>
  <h1>WebSocket 语音测试</h1>
  
  <div>
    <label>设备ID: <input type="text" id="deviceId" value="VIGIDOOR_001_RPI"></label>
    <button onclick="startCall()">发起呼叫</button>
    <button onclick="endCall()" disabled id="endBtn">挂断</button>
  </div>
  
  <div id="status" style="margin-top: 20px; padding: 10px; border: 1px solid #ccc;">
    状态: 未连接
  </div>
  
  <div id="log" style="margin-top: 20px; padding: 10px; border: 1px solid #ccc; height: 300px; overflow-y: scroll; font-family: monospace; font-size: 12px;">
  </div>

  <script>
    let socket = null;
    
    function log(message) {
      const logDiv = document.getElementById('log');
      const time = new Date().toLocaleTimeString();
      logDiv.innerHTML += `[${time}] ${message}<br>`;
      logDiv.scrollTop = logDiv.scrollHeight;
    }
    
    function setStatus(status) {
      document.getElementById('status').innerHTML = `状态: ${status}`;
    }
    
    async function startCall() {
      const deviceId = document.getElementById('deviceId').value;
      
      try {
        // 1. 调用 REST API 发起呼叫
        log('发起呼叫请求...');
        const response = await fetch('http://localhost:5002/api/v1/voice/call/initiate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ device_id: deviceId })
        });
        
        const result = await response.json();
        log(`呼叫响应: ${JSON.stringify(result)}`);
        
        if (!result.success) {
          alert('发起呼叫失败: ' + result.error);
          return;
        }
        
        // 2. 连接 WebSocket
        log('连接 WebSocket...');
        socket = io('http://localhost:5002');
        
        socket.on('connect', () => {
          log('WebSocket 已连接');
          setStatus('已连接');
          
          // 3. 加入会话
          socket.emit('browser_join', {
            device_id: deviceId,
            session_id: result.session_id
          });
        });
        
        socket.on('joined', (data) => {
          log(`已加入会话: ${JSON.stringify(data)}`);
          setStatus('等待设备...');
        });
        
        socket.on('call_established', (data) => {
          log(`通话已建立: ${JSON.stringify(data)}`);
          setStatus('通话中');
          document.getElementById('endBtn').disabled = false;
        });
        
        socket.on('audio_data', (data) => {
          log(`收到音频数据: ${data.timestamp}`);
        });
        
        socket.on('peer_hangup', () => {
          log('对方已挂断');
          setStatus('对方已挂断');
          endCall();
        });
        
        socket.on('peer_disconnected', () => {
          log('对方已断开');
          setStatus('对方已断开');
        });
        
        socket.on('error', (data) => {
          log(`错误: ${JSON.stringify(data)}`);
          setStatus('错误');
        });
        
        socket.on('disconnect', () => {
          log('WebSocket 已断开');
          setStatus('已断开');
        });
        
      } catch (error) {
        log(`异常: ${error.message}`);
        alert('发起呼叫异常: ' + error.message);
      }
    }
    
    function endCall() {
      if (socket) {
        log('挂断通话');
        socket.emit('hangup');
        socket.disconnect();
        socket = null;
        setStatus('已挂断');
        document.getElementById('endBtn').disabled = true;
      }
    }
    
    // 测试：发送音频数据
    function sendTestAudio() {
      if (socket) {
        socket.emit('audio_data', {
          audio: 'test_audio_data_from_browser',
          timestamp: Date.now()
        });
        log('已发送测试音频数据');
      }
    }
    
    // 页面关闭时自动挂断
    window.addEventListener('beforeunload', () => {
      endCall();
    });
  </script>
</body>
</html>
```

用浏览器打开 `test.html`，输入设备ID，点击"发起呼叫"。

---

## 🔧 故障排查

### 问题1：依赖安装失败

**症状**：`pip install` 报错

**解决**：
```bash
# 升级 pip
pip install --upgrade pip

# 使用国内镜像源
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

---

### 问题2：SocketIO 初始化失败

**症状**：启动时报错 `SocketIO 初始化失败`

**解决**：
```bash
# 检查 gevent 是否正确安装
python -c "import gevent; print(gevent.__version__)"

# 重新安装
pip uninstall gevent gevent-websocket -y
pip install gevent gevent-websocket
```

---

### 问题3：设备未收到 MQTT 通知

**症状**：调用 `/call/initiate` 后设备没有响应

**检查步骤**：
1. 确认华为云 IoTDA 配置正确
2. 检查设备是否在线
3. 确认设备已订阅 Topic: `vigidoor/down/{device_id}/command/stream`
4. 查看服务器日志：
   ```bash
   grep "IoTDA" logs/app.log
   ```

---

### 问题4：WebSocket 连接失败

**症状**：浏览器或设备连接 WebSocket 失败

**检查步骤**：
1. 确认服务器已启动
2. 检查防火墙是否开放 5002 端口
3. 浏览器控制台查看错误信息
4. 检查 CORS 配置

---

### 问题5：音频数据未转发

**症状**：一方发送，另一方收不到

**检查步骤**：
1. 确认双方都已连接（调用 `/call/status` API）
2. 查看服务器日志确认消息转发情况
3. 检查事件名称是否正确（必须是 `audio_data`）

---

## 📊 监控与日志

### 查看实时日志

```bash
# 实时查看所有日志
tail -f logs/app.log

# 只看 WebSocket 相关
tail -f logs/app.log | grep "WebSocket\|voice"

# 只看错误
tail -f logs/app.log | grep "ERROR\|WARNING"
```

### 查看会话统计

```bash
# 查看当前活跃会话
curl http://localhost:5002/api/v1/voice/sessions | python -m json.tool
```

---

## 🎉 下一步

- 📖 阅读 [WebSocket 语音功能文档](./docs/WEBSOCKET_VOICE.md)
- 🏗️ 阅读 [架构设计文档](./docs/ARCHITECTURE.md)
- 🔌 集成到你的浏览器/树莓派应用
- 🚀 部署到生产环境

---

**祝你使用愉快！** 🎊

如有问题，请查看日志或联系技术支持。
