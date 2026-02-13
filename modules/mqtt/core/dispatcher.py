"""
MQTT 消息分发器
负责接收、验证、去重和路由消息到对应的处理器
"""

from typing import Optional, Set
import logging
import time
from collections import deque

from modules.mqtt.core.base import MQTTMessageHandler
from modules.mqtt.topics import TopicManager
from modules.mqtt.messages import MessageFactory, CommandMessage
from modules.mqtt.publisher import MQTTPublisher
from core.ipc import IPCClient


class MQTTMessageDispatcher:
    """
    MQTT 消息分发器
    
    功能：
    1. 接收 MQTT 消息
    2. 基础验证（格式、时间戳、去重）
    3. 分发到对应的处理器
    4. 处理响应
    """
    
    def __init__(self, ipc: IPCClient, topic_manager: TopicManager,
                 publisher: MQTTPublisher,
                 logger: Optional[logging.Logger] = None):
        """
        初始化分发器
        
        Args:
            ipc: IPC 客户端
            topic_manager: 话题管理器
            publisher: MQTT 发布器
            logger: 日志记录器
        """
        self.ipc = ipc
        self.tm = topic_manager
        self.publisher = publisher
        self.logger = logger or logging.getLogger('mqtt_dispatcher')
        
        # 已处理的消息ID集合（用于去重）
        self.processed_msg_ids: Set[str] = set()
        self.msg_id_queue = deque(maxlen=1000)  # 保留最近1000条消息ID
        
        # 消息处理器列表
        self.handlers = []
        
        # 注册默认处理器
        self._register_default_handlers()
    
    def _register_default_handlers(self):
        """注册默认的消息处理器"""
        from modules.mqtt.handlers import (
            CommandStreamHandler,
            CommandAudioHandler,
            CommandDeviceHandler,
            ConfigUpdateHandler
        )
        
        default_handlers = [
            CommandStreamHandler(self.ipc, self.publisher, self.logger),
            CommandAudioHandler(self.ipc, self.publisher, self.logger),
            CommandDeviceHandler(self.ipc, self.publisher, self.logger),
            ConfigUpdateHandler(self.ipc, self.publisher, self.logger),
        ]
        
        for handler in default_handlers:
            self.register_handler(handler)
        
        self.logger.info(f"✅ 已注册 {len(self.handlers)} 个消息处理器")
    
    def register_handler(self, handler: MQTTMessageHandler):
        """注册消息处理器"""
        self.handlers.append(handler)
        self.logger.debug(f"注册处理器: {handler.__class__.__name__}")
    
    def dispatch(self, topic: str, payload: str) -> bool:
        """
        分发消息到对应处理器
        
        Args:
            topic: MQTT 话题
            payload: JSON 格式的消息负载
        
        Returns:
            是否成功处理
        """
        try:
            # 1. 解析消息
            message = MessageFactory.parse_message(topic, payload)
            if message is None:
                self.logger.warning(f"消息解析失败: {topic}，{payload}")
                return False
            
            # 2. 基础验证
            if not self._validate_message(message):
                return False
            
            # 3. 时间戳检查（防止重放攻击）
            # if self._is_expired(message):
            #     self.logger.warning(f"收到过期消息: {message.msg_id}")
            #     return False
            
            # 4. 去重检查
            if self._is_duplicate(message.msg_id):
                self.logger.debug(f"收到重复消息: {message.msg_id}")
                return False
            
            # 5. 记录消息ID
            self._record_msg_id(message.msg_id)
            
            # 6. 分发到处理器
            if not isinstance(message, CommandMessage):
                self.logger.debug(f"收到非指令消息: {topic}")
                return True
            
            for handler in self.handlers:
                if handler.can_handle(topic, message):
                    return handler.handle(topic, message)
            
            self.logger.warning(f"未找到处理器: {topic}")
            return False
            
        except Exception as e:
            self.logger.error(f"消息分发失败: {e}", exc_info=True)
            return False
    
    def _validate_message(self, message) -> bool:
        """基础消息验证"""
        # 检查必填字段
        if not message.msg_id:
            self.logger.warning("消息缺少 msg_id 字段")
            return False
        
        if not message.device_id:
            self.logger.warning("消息缺少 device_id 字段")
            return False
        
        # 验证设备ID是否匹配
        if message.device_id != self.tm.device_id:
            self.logger.warning(
                f"设备ID不匹配: 期望 {self.tm.device_id}, "
                f"实际 {message.device_id}"
            )
            return False
        
        return True
    
    def _is_expired(self, message, max_age_seconds: int = 300) -> bool:
        """
        检查消息是否过期
        
        Args:
            message: 消息对象
            max_age_seconds: 最大允许的消息年龄（秒），默认5分钟
        
        Returns:
            是否过期
        """
        if not message.timestamp:
            return False
        
        now_ms = int(time.time() * 1000)
        age_ms = now_ms - message.timestamp
        
        return age_ms > (max_age_seconds * 1000)
    
    def _is_duplicate(self, msg_id: str) -> bool:
        """检查消息ID是否重复"""
        return msg_id in self.processed_msg_ids
    
    def _record_msg_id(self, msg_id: str):
        """记录已处理的消息ID"""
        self.processed_msg_ids.add(msg_id)
        self.msg_id_queue.append(msg_id)
        
        # 清理过旧的消息ID（保持集合大小）
        if len(self.msg_id_queue) >= self.msg_id_queue.maxlen:
            # 移除最旧的消息ID
            oldest_id = self.msg_id_queue[0]
            if oldest_id in self.processed_msg_ids:
                self.processed_msg_ids.discard(oldest_id)
    
    def clear_processed_ids(self):
        """清空已处理的消息ID记录"""
        self.processed_msg_ids.clear()
        self.msg_id_queue.clear()
        self.logger.info("已清空消息ID记录")
