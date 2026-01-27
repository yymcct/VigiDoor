"""
MQTT 通信进程
"""

import time
import json
import threading
from utils.logger import setup_logger
from utils.ipc import IPCHelper
from utils.mqtt_topics import TopicManager
from utils.mqtt_publisher import MQTTPublisher
from utils.mqtt_handlers import MQTTMessageDispatcher

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
        
        self.topic_manager = TopicManager(self.device_id)
        self.publisher = None  # 延迟初始化（需要 MQTT client）
        self.dispatcher = None  # 延迟初始化
        
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
            
            # 设置遗嘱消息（设备离线）
            offline_topic = self.topic_manager.build(TopicManager.LIFECYCLE_OFFLINE)
            from utils.mqtt_messages import LifecycleOfflineMessage
            offline_msg = LifecycleOfflineMessage(
                device_id=self.device_id,
                data={"reason": "unexpected", "last_heartbeat": int(time.time() * 1000)}
            )
            self.client.will_set(
                topic=offline_topic,
                payload=offline_msg.to_json(),
                qos=1,
                retain=True
            )
            
            # 设置认证（如果需要）
            username = self.config['mqtt'].get('username')
            password = self.config['mqtt'].get('password')
            if username and password:
                self.client.username_pw_set(username, password)
            
            # 初始化发布器和分发器
            self.publisher = MQTTPublisher(self.client, self.topic_manager, logger)
            self.dispatcher = MQTTMessageDispatcher(
                self.ipc, self.topic_manager, self.publisher, logger
            )
            
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
            
            # 使用 TopicManager 获取订阅列表
            subscribe_topics = self.topic_manager.get_device_subscribe_topics()
            self.client.subscribe(subscribe_topics)
            logger.info(f"📥 已订阅主题: {[t[0] for t in subscribe_topics]}")
            
            # 发送上线消息
            self._publish_online_status()
            
            # 发送缓存的消息
            self.publisher.flush_buffer()
            
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
            topic = msg.topic
            payload = msg.payload.decode()
            logger.info(f"📥 收到消息: {topic}")
            
            self.dispatcher.dispatch(topic, payload)
            
        except Exception as e:
            logger.error(f"处理 MQTT 消息失败: {e}", exc_info=True)
    
    def _publish_online_status(self):
        """发布上线消息"""
        try:
            from utils.mqtt_messages import LifecycleOnlineMessage
            
            online_msg = LifecycleOnlineMessage(
                device_id=self.device_id,
                data={
                    "device_name": self.config['device']['name'],
                    "firmware_version": self.config['device'].get('firmware_version', '1.0.0')
                }
            )
            
            self.publisher.publish(online_msg, retain=True)
            logger.info("📤 已发送上线消息")
            
        except Exception as e:
            logger.error(f"发送上线消息失败: {e}")
    
    def _heartbeat_loop(self):
        """心跳循环"""
        while self.running:
            if self.is_connected:
                try:
                    # 获取当前全局状态
                    global_state = self.state.get('global_state', 'safe')
                    uptime = int(time.time() - self.state.get('start_time', time.time()))
                    
                    # 使用 Publisher 发送心跳
                    self.publisher.publish_lifecycle_heartbeat(
                        uptime=uptime,
                        global_state=global_state
                    )
                    
                except Exception as e:
                    logger.error(f"心跳发送失败: {e}")
                    self.is_connected = False
            
            # 同时发送 IPC 心跳
            self.ipc.send_heartbeat()
            
            time.sleep(30)
    
    def _ipc_message_handler(self):
        """处理来自其他进程的消息"""
        while self.running:
            data = msg.get('data', {})
            msg = self.ipc.receive(timeout=1.0)
            if msg:
                self._handle_ipc_message(msg)
                
    
    def _handle_ipc_message(self, msg):
        """处理 IPC 消息"""
        msg_type = msg.get('type')
        data = msg.get('data', {})
        
        if msg_type == 'report_alarm':
            # 判断告警类型并上报
            alarm_type = data.get('alarm_type', '')
            if 'audio' in alarm_type or 'sound' in alarm_type:
                self.publisher.publish_alarm_audio(data)
            elif 'vision' in alarm_type or 'person' in alarm_type or 'object' in alarm_type:
                self.publisher.publish_alarm_vision(data)
            else:
                # 默认作为视觉告警
                self.publisher.publish_alarm_vision(data)
            logger.info("📤 告警已上报")
            
        elif msg_type == 'report_health':
            # 上报健康状态
            self.publisher.publish_health_metrics(data)
            logger.debug("📤 健康状态已上报")
            
        elif msg_type == 'critical_alarm':
            # 严重系统告警
            self.publisher.publish_alarm_system(data)
            logger.error("📤 严重告警已上报")
        
        elif msg_type == 'stream_status_changed':
            # 推流状态变更
            self.publisher.publish_status_stream(data)
            logger.info("📤 推流状态已上报")
        
        elif msg_type == 'hardware_status_changed':
            # 硬件状态变更
            self.publisher.publish_status_hardware(data)
            logger.info("📤 硬件状态已上报")
        
        elif msg_type == 'process_status_changed':
            # 进程状态变更
            self.publisher.publish_health_process(data)
            logger.info("📤 进程状态已上报")
        
        elif msg_type == 'shutdown':
            logger.info("收到关闭信号")
            self.running = False