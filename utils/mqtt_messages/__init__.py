"""
MQTT 消息模块
使用 dataclass 定义标准化的消息结构，支持自动序列化和验证

使用方式：
    from utils.mqtt_messages import AlarmVisionMessage, MessageFactory
    
    # 创建消息
    msg = AlarmVisionMessage(
        device_id="RPI_001",
        data={"alarm_type": "person_detected", "confidence": 0.95}
    )
    
    # 解析消息
    parsed_msg = MessageFactory.parse_message(topic, payload)
"""

# 导出基类
from .base import MQTTMessageBase

# 导出生命周期消息
from .lifecycle import (
    LifecycleOnlineMessage,
    LifecycleOfflineMessage,
    LifecycleHeartbeatMessage
)

# 导出告警消息
from .alarm import (
    AlarmVisionMessage,
    AlarmAudioMessage,
    AlarmSystemMessage
)

# 导出健康状态消息
from .health import (
    HealthMetricsMessage,
    HealthProcessMessage
)

# 导出业务状态消息
from .status import (
    StatusStreamMessage,
    StatusHardwareMessage
)

# 导出响应和日志消息
from .response import (
    ResponseMessage,
    LogErrorMessage
)

# 导出指令消息
from .command import CommandMessage

# 导出消息工厂
from .factory import MessageFactory


# 定义公共接口（用于 from utils.mqtt_messages import *）
__all__ = [
    # 基类
    'MQTTMessageBase',
    
    # 生命周期消息
    'LifecycleOnlineMessage',
    'LifecycleOfflineMessage',
    'LifecycleHeartbeatMessage',
    
    # 告警消息
    'AlarmVisionMessage',
    'AlarmAudioMessage',
    'AlarmSystemMessage',
    
    # 健康状态消息
    'HealthMetricsMessage',
    'HealthProcessMessage',
    
    # 业务状态消息
    'StatusStreamMessage',
    'StatusHardwareMessage',
    
    # 响应和日志消息
    'ResponseMessage',
    'LogErrorMessage',
    
    # 指令消息
    'CommandMessage',
    
    # 工厂类
    'MessageFactory',
]
