"""
MQTT 通信进程
负责与云平台通信
"""

import time
import json
import threading
from utils.logger import setup_logger
from utils.ipc import IPCHelper

logger = setup_logger('mqtt_client')


class MQTTClientProcess:
    """
    MQTT 通信进程 - 负责与云平台通信
    
    功能：
    1. 连接 MQTT Broker（华为云 IoT）
    2. 订阅平台指令主题
    3. 上报告警、心跳、健康状态
    4. 处理平台下发的控制指令
    """
    
    def __init__(self, ipc_queue, shared_state, config):
        self.ipc = IPCHelper(ipc_queue, 'mqtt_client')
        self.state = shared_state
        self.config = config
        self.running = True
        
        # MQTT 配置
        self.broker_host = config['mqtt']['broker_host']
        self.broker_port = config['mqtt']['broker_port']
        self.device_id = config['device']['id']
        
        self.client = None
        self.is_connected = False
        
        # 消息缓存队列
        self.message_buffer = []
        self.max_buffer_size = 100
        
        logger.info(f"MQTT 通信进程初始化完成")
        logger.info(f"  Broker: {self.broker_host}:{self.broker_port}")
        logger.info(f"  设备 ID: {self.device_id}")
    
    def run(self):
        """主循环"""
        logger.info("📡 MQTT 通信进程启动")
        
        # 初始化 MQTT 客户端
        self._init_client()
        
        # 启动子线程
        threading.Thread(target=self._heartbeat_loop, daemon=True).start()
        threading.Thread(target=self._ipc_message_handler, daemon=True).start()
        
        # 连接循环
        while self.running:
            if not self.is_connected:
                self._connect()
            time.sleep(5)
        
        logger.info("MQTT 通信进程退出")
    
    def _init_client(self):
        """初始化 MQTT 客户端"""
        try:
            import paho.mqtt.client as mqtt
            
            self.client = mqtt.Client(
                client_id=f"{self.config['mqtt']['client_id_prefix']}_{self.device_id}",
                clean_session=False
            )
            
            # 设置回调
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message
            
            # 设置遗嘱消息
            topics = self.config['mqtt']['topics']
            status_topic = topics['status'].format(device_id=self.device_id)
            self.client.will_set(
                topic=status_topic,
                payload=json.dumps({"online": False, "timestamp": time.time()}),
                qos=1,
                retain=True
            )
            
            # 设置认证（如果需要）
            username = self.config['mqtt'].get('username')
            password = self.config['mqtt'].get('password')
            if username and password:
                self.client.username_pw_set(username, password)
            
            logger.info("✅ MQTT 客户端初始化成功")
            
        except Exception as e:
            logger.error(f"MQTT 客户端初始化失败: {e}")
    
    def _connect(self):
        """连接 MQTT 服务器"""
        try:
            logger.info(f"🔄 尝试连接 MQTT 服务器...")
            
            self.client.connect(
                host=self.broker_host,
                port=self.broker_port,
                keepalive=self.config['mqtt']['keepalive']
            )
            
            # 启动网络循环
            self.client.loop_start()
            
        except Exception as e:
            logger.error(f"❌ MQTT 连接失败: {e}")
            time.sleep(10)
    
    def _on_connect(self, client, userdata, flags, rc):
        """连接成功回调"""
        if rc == 0:
            logger.info("✅ MQTT 连接成功")
            self.is_connected = True
            
            # 订阅指令主题
            topics = self.config['mqtt']['topics']
            qos = self.config['mqtt']['qos']
            
            subscribe_topics = [
                (topics['command'].format(device_id=self.device_id), qos),
                (topics['config'].format(device_id=self.device_id), qos),
            ]
            self.client.subscribe(subscribe_topics)
            logger.info(f"📥 已订阅主题: {[t[0] for t in subscribe_topics]}")
            
            # 发送上线消息
            self._publish_online_status()
            
            # 发送缓存的消息
            self._flush_message_buffer()
            
        else:
            logger.error(f"❌ MQTT 连接失败，返回码: {rc}")
            self.is_connected = False
    
    def _on_disconnect(self, client, userdata, rc):
        """断线回调"""
        logger.warning(f"⚠️ MQTT 连接断开，返回码: {rc}")
        self.is_connected = False
        
        if rc != 0:
            logger.warning("异常断线，将自动重连")
    
    def _on_message(self, client, userdata, msg):
        """收到消息回调"""
        try:
            payload = json.loads(msg.payload.decode())
            logger.info(f"📥 收到平台指令: {payload}")
            
            # 转发给 Supervisor
            self.ipc.send(
                msg_type='mqtt_command',
                target='supervisor',
                data={
                    'action': payload.get('action'),
                    'data': payload.get('data')
                }
            )
            
        except Exception as e:
            logger.error(f"处理 MQTT 消息失败: {e}")
    
    def _publish_online_status(self):
        """发布上线消息"""
        topics = self.config['mqtt']['topics']
        status_topic = topics['status'].format(device_id=self.device_id)
        
        payload = json.dumps({
            "online": True,
            "timestamp": time.time(),
            "device_name": self.config['device']['name']
        })
        
        self.client.publish(status_topic, payload, qos=1, retain=True)
        logger.info("📤 已发送上线消息")
    
    def _heartbeat_loop(self):
        """心跳循环"""
        topics = self.config['mqtt']['topics']
        heartbeat_topic = topics['heartbeat'].format(device_id=self.device_id)
        
        while self.running:
            if self.is_connected:
                try:
                    payload = json.dumps({"timestamp": time.time()})
                    self.client.publish(heartbeat_topic, payload, qos=0)
                except Exception as e:
                    logger.error(f"心跳发送失败: {e}")
                    self.is_connected = False
            
            # 同时发送 IPC 心跳
            self.ipc.send_heartbeat()
            
            time.sleep(30)
    
    def _ipc_message_handler(self):
        """处理来自其他进程的消息"""
        while self.running:
            msg = self.ipc.receive(timeout=1.0)
            if msg:
                self._handle_ipc_message(msg)
    
    def _handle_ipc_message(self, msg):
        """处理 IPC 消息"""
        msg_type = msg.get('type')
        
        if msg_type == 'report_alarm':
            # 上报告警
            self._publish_alarm(msg.get('data', {}))
            
        elif msg_type == 'report_health':
            # 上报健康状态
            self._publish_health(msg.get('data', {}))
            
        elif msg_type == 'critical_alarm':
            # 严重告警
            self._publish_critical_alarm(msg.get('data', {}))
        
        elif msg_type == 'shutdown':
            logger.info("收到关闭信号")
            self.running = False
    
    def _publish_alarm(self, alarm_data: dict):
        """发布告警消息"""
        topics = self.config['mqtt']['topics']
        alarm_topic = topics['alarm'].format(device_id=self.device_id)
        
        payload = json.dumps(alarm_data)
        
        if self.is_connected:
            self.client.publish(alarm_topic, payload, qos=1)
            logger.info("📤 告警已上报")
        else:
            # 缓存消息
            self._buffer_message(alarm_topic, payload, qos=1)
    
    def _publish_health(self, health_data: dict):
        """发布健康状态"""
        topics = self.config['mqtt']['topics']
        health_topic = topics['health'].format(device_id=self.device_id)
        
        payload = json.dumps(health_data)
        
        if self.is_connected:
            self.client.publish(health_topic, payload, qos=0)
            logger.debug("📤 健康状态已上报")
    
    def _publish_critical_alarm(self, alarm_data: dict):
        """发布严重告警"""
        topics = self.config['mqtt']['topics']
        alarm_topic = topics['alarm'].format(device_id=self.device_id)
        
        payload = json.dumps(alarm_data)
        
        if self.is_connected:
            self.client.publish(alarm_topic, payload, qos=2)  # QoS 2 确保送达
            logger.error("📤 严重告警已上报")
    
    def _buffer_message(self, topic, payload, qos):
        """缓存消息"""
        if len(self.message_buffer) < self.max_buffer_size:
            self.message_buffer.append((topic, payload, qos))
            logger.warning(f"⚠️ MQTT 未连接，消息已缓存（队列: {len(self.message_buffer)}）")
        else:
            logger.error("❌ 消息缓存队列已满，丢弃消息")
    
    def _flush_message_buffer(self):
        """发送缓存的消息"""
        if self.message_buffer:
            logger.info(f"📤 发送缓存的 {len(self.message_buffer)} 条消息")
            
            for topic, payload, qos in self.message_buffer:
                self.client.publish(topic, payload, qos)
            
            self.message_buffer.clear()
