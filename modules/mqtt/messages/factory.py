"""
MQTT 消息工厂模块
根据话题创建、解析对应的消息对象
"""

from typing import Optional
import json

from .base import MQTTMessageBase
from .lifecycle import (
    LifecycleOnlineMessage,
    LifecycleOfflineMessage,
    LifecycleHeartbeatMessage
)
from .alarm import (
    AlarmIntrusionMessage,
    AlarmSystemMessage
)
from .health import (
    HealthMetricsMessage,
    HealthProcessMessage
)
from .status import (
    StatusStreamMessage,
    StatusHardwareMessage
)
from .response import (
    ResponseMessage,
    LogErrorMessage
)
from .command import CommandMessage


class MessageFactory:
    """消息工厂 - 根据话题创建对应的消息对象"""
    
    # 话题关键字到消息类的映射
    MESSAGE_TYPE_MAP = {
        # 生命周期
        'lifecycle/online': LifecycleOnlineMessage,
        'lifecycle/offline': LifecycleOfflineMessage,
        'lifecycle/heartbeat': LifecycleHeartbeatMessage,
        
        # 告警
        'alarm/intrusion': AlarmIntrusionMessage,
        'alarm/system': AlarmSystemMessage,
        
        # 健康
        'health/metrics': HealthMetricsMessage,
        'health/process': HealthProcessMessage,
        
        # 状态
        'status/stream': StatusStreamMessage,
        'status/hardware': StatusHardwareMessage,
        
        # 日志
        'log/error': LogErrorMessage,
        
        # 响应
        'response/': ResponseMessage,
        
        # 指令（下行）
        'command/': CommandMessage,
        'config/': CommandMessage,
    }
    
    @classmethod
    def create_from_topic(cls, topic: str, device_id: str, data: dict = None) -> MQTTMessageBase:
        """
        根据话题创建对应的消息对象
        
        Args:
            topic: MQTT 话题
            device_id: 设备ID
            data: 消息数据
        
        Returns:
            对应的消息对象
        
        Examples:
            >>> msg = MessageFactory.create_from_topic(
            ...     "vigidoor/up/RPI_001/alarm/intrusion",
            ...     "RPI_001",
            ...     {"alarm_type": "person_detected", "confidence": 0.95}
            ... )
            >>> isinstance(msg, AlarmIntrusionMessage)
            True
        """
        # 查找匹配的消息类型
        for keyword, message_class in cls.MESSAGE_TYPE_MAP.items():
            if keyword in topic:
                return message_class(device_id=device_id, data=data or {})
        
        # 默认返回基类
        return MQTTMessageBase(device_id=device_id)
    
    @classmethod
    def parse_message(cls, topic: str, payload: str) -> Optional[MQTTMessageBase]:
        """
        解析收到的 MQTT 消息
        
        Args:
            topic: MQTT 话题
            payload: JSON 格式的消息负载
        
        Returns:
            解析后的消息对象，失败返回 None
        """
        try:
            data = json.loads(payload)
            
            # 如果消息外层有包装（如有 content 字段），则提取真实内容
            if 'content' in data and isinstance(data['content'], dict):
                data = data['content']
            
            # 根据话题创建对应的消息对象
            for keyword, message_class in cls.MESSAGE_TYPE_MAP.items():
                if keyword in topic:
                    # 过滤出消息类支持的字段
                    valid_fields = cls._filter_valid_fields(message_class, data)
                    return message_class(**valid_fields)
            
            # 默认解析为基类
            valid_fields = cls._filter_valid_fields(MQTTMessageBase, data)
            return MQTTMessageBase(**valid_fields)
            
        except Exception as e:
            print(f"消息解析失败: {e}")
            return None
    
    @staticmethod
    def _filter_valid_fields(message_class, data: dict) -> dict:
        """
        过滤出 dataclass 支持的字段
        
        Args:
            message_class: 消息类
            data: 原始数据字典
        
        Returns:
            只包含 dataclass 定义字段的字典
        """
        from dataclasses import fields as dataclass_fields
        
        # 使用 dataclasses.fields() 获取所有字段（包括继承的）
        try:
            valid_field_names = {f.name for f in dataclass_fields(message_class)}
        except Exception:
            # 如果不是 dataclass，返回空字典
            return {}
        
        # 只保留有效字段
        return {k: v for k, v in data.items() if k in valid_field_names}
