"""
WebSocket 测试客户端
用于测试浏览器端和设备端的 WebSocket 连接
"""
import socketio
import time
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestClient:
    """测试客户端"""
    
    def __init__(self, server_url: str, client_type: str, device_id: str):
        self.server_url = server_url
        self.client_type = client_type  # "browser" or "device"
        self.device_id = device_id
        self.session_id = device_id  # 使用 device_id 作为 session_id
        
        self.sio = socketio.Client(logger=False, engineio_logger=False)
        self._register_events()
    
    def _register_events(self):
        """注册事件处理器"""
        
        @self.sio.event
        def connect():
            logger.info(f"[{self.client_type}] 已连接到服务器")
        
        @self.sio.event
        def disconnect():
            logger.info(f"[{self.client_type}] 已断开连接")
        
        @self.sio.event
        def server_ready(data):
            logger.info(f"[{self.client_type}] 服务器就绪: {data}")
        
        @self.sio.event
        def joined(data):
            logger.info(f"[{self.client_type}] 已加入会话: {data}")
        
        @self.sio.event
        def call_established(data):
            logger.info(f"[{self.client_type}] 通话已建立: {data}")
        
        @self.sio.event
        def audio_data(data):
            logger.info(f"[{self.client_type}] 收到音频数据: {len(str(data))} bytes")
        
        @self.sio.event
        def peer_disconnected(data):
            logger.warning(f"[{self.client_type}] 对方已断开: {data}")
        
        @self.sio.event
        def peer_hangup(data):
            logger.warning(f"[{self.client_type}] 对方已挂断: {data}")
        
        @self.sio.event
        def call_terminated(data):
            logger.warning(f"[{self.client_type}] 通话已终止: {data}")
        
        @self.sio.event
        def error(data):
            logger.error(f"[{self.client_type}] 错误: {data}")
    
    def connect(self):
        """连接到服务器"""
        logger.info(f"[{self.client_type}] 正在连接到 {self.server_url}...")
        self.sio.connect(self.server_url)
        time.sleep(0.5)
        
        # 加入会话
        if self.client_type == "browser":
            self.sio.emit('browser_join', {
                'device_id': self.device_id,
                'session_id': self.session_id
            })
        else:
            self.sio.emit('device_join', {
                'device_id': self.device_id,
                'session_id': self.session_id
            })
    
    def send_audio(self, audio_data: bytes):
        """发送音频数据"""
        self.sio.emit('audio_data', {
            'audio': audio_data,
            'timestamp': int(time.time() * 1000)
        })
        logger.info(f"[{self.client_type}] 已发送音频数据: {len(audio_data)} bytes")
    
    def ping(self):
        """发送心跳"""
        self.sio.emit('ping')
    
    def hangup(self):
        """挂断"""
        logger.info(f"[{self.client_type}] 挂断通话")
        self.sio.emit('hangup')
    
    def disconnect_socket(self):
        """断开连接"""
        self.sio.disconnect()
    
    def wait(self):
        """等待（阻塞）"""
        self.sio.wait()


def test_scenario_1():
    """
    测试场景1：浏览器和设备正常连接、通话、挂断
    """
    print("\n========== 测试场景1：正常通话流程 ==========\n")
    
    server_url = "http://localhost:5002"
    device_id = "VIGIDOOR_TEST_RPI"
    
    # 1. 创建浏览器客户端
    browser = TestClient(server_url, "browser", device_id)
    
    # 2. 创建设备客户端
    device = TestClient(server_url, "device", device_id)
    
    try:
        # 3. 浏览器先连接
        logger.info("步骤1: 浏览器连接...")
        browser.connect()
        time.sleep(2)
        
        # 4. 设备连接
        logger.info("步骤2: 设备连接...")
        device.connect()
        time.sleep(2)
        
        # 5. 浏览器发送音频
        logger.info("步骤3: 浏览器发送音频...")
        browser.send_audio(b"audio_from_browser_123456")
        time.sleep(1)
        
        # 6. 设备发送音频
        logger.info("步骤4: 设备发送音频...")
        device.send_audio(b"audio_from_device_abcdef")
        time.sleep(1)
        
        # 7. 心跳测试
        logger.info("步骤5: 心跳测试...")
        browser.ping()
        device.ping()
        time.sleep(1)
        
        # 8. 浏览器主动挂断
        logger.info("步骤6: 浏览器挂断...")
        browser.hangup()
        time.sleep(2)
        
        print("\n✅ 测试场景1 完成\n")
    
    except Exception as e:
        logger.exception(f"测试失败: {e}")
    
    finally:
        browser.disconnect_socket()
        device.disconnect_socket()


def test_scenario_2():
    """
    测试场景2：只有浏览器连接（设备未响应）
    """
    print("\n========== 测试场景2：单方连接超时 ==========\n")
    
    server_url = "http://localhost:5002"
    device_id = "VIGIDOOR_TIMEOUT_TEST"
    
    browser = TestClient(server_url, "browser", device_id)
    
    try:
        logger.info("浏览器连接，设备不连接，等待超时...")
        browser.connect()
        
        # 等待一段时间观察
        for i in range(10):
            time.sleep(1)
            logger.info(f"等待中... {i+1}/10")
        
        print("\n✅ 测试场景2 完成（需手动检查服务器日志确认超时清理）\n")
    
    except Exception as e:
        logger.exception(f"测试失败: {e}")
    
    finally:
        browser.disconnect_socket()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法:")
        print("  python test_websocket_client.py scenario1   # 正常通话流程")
        print("  python test_websocket_client.py scenario2   # 单方连接超时")
        print("  python test_websocket_client.py browser <device_id>   # 浏览器客户端")
        print("  python test_websocket_client.py device <device_id>    # 设备客户端")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "scenario1":
        test_scenario_1()
    
    elif command == "scenario2":
        test_scenario_2()
    
    elif command in ["browser", "device"]:
        if len(sys.argv) < 3:
            print(f"错误: 需要指定 device_id")
            sys.exit(1)
        
        device_id = sys.argv[2]
        server_url = "http://localhost:5002"
        
        client = TestClient(server_url, command, device_id)
        
        try:
            client.connect()
            
            # 保持连接，接收消息
            logger.info(f"{command} 客户端已启动，按 Ctrl+C 退出")
            client.wait()
        
        except KeyboardInterrupt:
            logger.info("用户中断")
        
        finally:
            client.disconnect_socket()
    
    else:
        print(f"未知命令: {command}")
        sys.exit(1)
