"""
MQTT 消息处理器框架
处理从平台下发的 MQTT 指令，支持验证、去重、路由和响应
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable, Set
import logging
import time
from collections import deque

from utils.mqtt_topics import TopicManager
from utils.mqtt_messages import MessageFactory, CommandMessage
from utils.mqtt_publisher import MQTTPublisher
from utils.ipc import IPCHelper


class MQTTMessageHandler(ABC):
    """MQTT 消息处理器基类"""
    
    def __init__(self, ipc: IPCHelper, publisher: MQTTPublisher, 
                 logger: Optional[logging.Logger] = None):
        """
        初始化消息处理器
        
        Args:
            ipc: IPC 通信助手
            publisher: MQTT 发布器
            logger: 日志记录器
        """
        self.ipc = ipc
        self.publisher = publisher
        self.logger = logger or logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def can_handle(self, topic: str, message: CommandMessage) -> bool:
        """
        判断是否可以处理该消息
        
        Args:
            topic: MQTT 话题
            message: 解析后的消息对象
        
        Returns:
            是否可以处理
        """
        pass
    
    @abstractmethod
    def handle(self, topic: str, message: CommandMessage) -> bool:
        """
        处理消息
        
        Args:
            topic: MQTT 话题
            message: 解析后的消息对象
        
        Returns:
            是否处理成功
        """
        pass
    
    def send_response(self, command_type: str, request_msg_id: str,
                     status: str, message: str = "", error_code: Optional[int] = None):
        """
        发送响应消息
        
        Args:
            command_type: 指令类型（stream/audio/device）
            request_msg_id: 原始请求的消息ID
            status: 响应状态（success/failed/timeout）
            message: 响应消息
            error_code: 错误码
        """
        self.publisher.publish_response(
            command_type=command_type,
            request_msg_id=request_msg_id,
            status=status,
            message=message,
            error_code=error_code
        )


class CommandStreamHandler(MQTTMessageHandler):
    """推流控制指令处理器"""
    
    def can_handle(self, topic: str, message: CommandMessage) -> bool:
        return "/command/stream" in topic
    
    def handle(self, topic: str, message: CommandMessage) -> bool:
        """
        处理推流控制指令
        
        支持的动作：
        - start: 开始推流
        - stop: 停止推流
        """
        action = message.get_action()
        self.logger.info(f"📥 收到推流控制指令: {action}")
        
        try:
            if action == 'start':
                # 转发给 stream_manager 进程
                self.ipc.send(
                    msg_type='start_stream',
                    target='stream_manager',
                    data=message.data
                )
                self.send_response('stream', message.msg_id, 'success', '推流指令已接收')
                
            elif action == 'stop':
                # 转发给 stream_manager 进程
                self.ipc.send(
                    msg_type='stop_stream',
                    target='stream_manager'
                )
                self.send_response('stream', message.msg_id, 'success', '停止推流指令已接收')
                
            else:
                self.logger.warning(f"未知的推流指令: {action}")
                self.send_response('stream', message.msg_id, 'failed', 
                                 f'未知的指令: {action}', error_code=1000)
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"处理推流指令失败: {e}", exc_info=True)
            self.send_response('stream', message.msg_id, 'failed', 
                             str(e), error_code=5000)
            return False


class CommandAudioHandler(MQTTMessageHandler):
    """音频控制指令处理器（远程喊话）"""
    
    def can_handle(self, topic: str, message: CommandMessage) -> bool:
        return "/command/audio" in topic
    
    def handle(self, topic: str, message: CommandMessage) -> bool:
        """
        处理音频控制指令
        
        支持的动作：
        - speak: 远程喊话
        """
        action = message.get_action()
        self.logger.info(f"📥 收到音频控制指令: {action}")
        
        try:
            if action == 'speak':
                # 转发给 audio_processor 进程
                self.ipc.send(
                    msg_type='play_audio',
                    target='audio_processor',
                    data=message.data
                )
                self.send_response('audio', message.msg_id, 'success', '喊话指令已接收')
                
            else:
                self.logger.warning(f"未知的音频指令: {action}")
                self.send_response('audio', message.msg_id, 'failed', 
                                 f'未知的指令: {action}', error_code=1000)
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"处理音频指令失败: {e}", exc_info=True)
            self.send_response('audio', message.msg_id, 'failed', 
                             str(e), error_code=5000)
            return False


class CommandDeviceHandler(MQTTMessageHandler):
    """设备控制指令处理器"""
    
    def can_handle(self, topic: str, message: CommandMessage) -> bool:
        return "/command/device" in topic
    
    def handle(self, topic: str, message: CommandMessage) -> bool:
        """
        处理设备控制指令
        
        支持的动作：
        - reboot: 重启设备
        - set_light: 控制灯带
        """
        action = message.get_action()
        self.logger.info(f"📥 收到设备控制指令: {action}")
        
        try:
            if action == 'reboot':
                # 重启设备
                delay = message.data.get('delay', 5)
                self.send_response('device', message.msg_id, 'success', 
                                 f'设备将在 {delay} 秒后重启')
                # TODO: 实现重启逻辑
                
            elif action == 'set_light':
                # 控制灯带
                self.ipc.send(
                    msg_type='set_light',
                    target='device_controller',
                    data=message.data
                )
                self.send_response('device', message.msg_id, 'success', '灯带控制指令已接收')
                
            else:
                self.logger.warning(f"未知的设备指令: {action}")
                self.send_response('device', message.msg_id, 'failed', 
                                 f'未知的指令: {action}', error_code=1000)
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"处理设备指令失败: {e}", exc_info=True)
            self.send_response('device', message.msg_id, 'failed', 
                             str(e), error_code=5000)
            return False


class ConfigUpdateHandler(MQTTMessageHandler):
    """配置更新指令处理器"""
    
    def can_handle(self, topic: str, message: CommandMessage) -> bool:
        return "/config/update" in topic
    
    def handle(self, topic: str, message: CommandMessage) -> bool:
        """处理配置更新指令"""
        self.logger.info(f"📥 收到配置更新指令")
        
        try:
            config_items = message.data.get('config_items', {})
            apply_immediately = message.data.get('apply_immediately', False)
            
            # TODO: 实现配置更新逻辑
            # 1. 验证配置项
            # 2. 更新配置文件
            # 3. 如果 apply_immediately=True，通知各进程重新加载配置
            
            self.logger.info(f"更新配置项: {list(config_items.keys())}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"处理配置更新失败: {e}", exc_info=True)
            return False


class MQTTMessageDispatcher:
    """
    MQTT 消息分发器
    
    功能：
    1. 接收 MQTT 消息
    2. 基础验证（格式、时间戳、去重）
    3. 分发到对应的处理器
    4. 处理响应
    """
    
    def __init__(self, ipc: IPCHelper, topic_manager: TopicManager,
                 publisher: MQTTPublisher,
                 logger: Optional[logging.Logger] = None):
        """
        初始化分发器
        
        Args:
            ipc: IPC 通信助手
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
                self.logger.warning(f"消息解析失败: {topic}")
                return False
            
            # 2. 基础验证
            if not self._validate_message(message):
                return False
            
            # 3. 时间戳检查（防止重放攻击）
            if self._is_expired(message):
                self.logger.warning(f"收到过期消息: {message.msg_id}")
                return False
            
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
