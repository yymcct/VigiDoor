"""
MQTT 消息处理器基类
定义处理器的抽象接口
"""

from abc import ABC, abstractmethod
from typing import Optional
import logging

from modules.mqtt.messages import CommandMessage
from modules.mqtt.publisher import MQTTPublisher
from core.ipc import IPCClient


class MQTTMessageHandler(ABC):
    """MQTT 消息处理器基类"""
    
    def __init__(self, ipc: IPCClient, publisher: MQTTPublisher, 
                 logger: Optional[logging.Logger] = None):
        """
        初始化消息处理器
        
        Args:
            ipc: IPC 客户端
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
    #TODO 应答消息要和华为云再联合调试一下
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
