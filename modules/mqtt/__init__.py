"""
MQTT 模块
提供完整的 MQTT 通信功能，包括：
- 话题管理
- 消息发布
- 消息定义
- 消息处理和分发

使用示例：
    from modules.mqtt import TopicManager, MQTTPublisher, MQTTMessageDispatcher
    
    # 初始化话题管理器
    tm = TopicManager(device_id="RPI_001")
    
    # 初始化发布器
    publisher = MQTTPublisher(mqtt_client, tm)
    
    # 初始化分发器
    dispatcher = MQTTMessageDispatcher(ipc, tm, publisher)
"""

# 导出话题管理器
from .topics import TopicManager

# 导出消息发布器
from .publisher import MQTTPublisher

# 导出核心框架
from .core import MQTTMessageHandler, MQTTMessageDispatcher

# 导出 MQTT 客户端进程
from .process import MQTTClientProcess

# 导出消息类型（可选，方便外部使用）
from .messages import (
    MessageFactory,
    CommandMessage,
    # 生命周期消息
    LifecycleOnlineMessage,
    LifecycleOfflineMessage,
    LifecycleHeartbeatMessage,
    # 告警消息
    AlarmIntrusionMessage,
    AlarmSystemMessage,
    # 健康状态消息
    HealthMetricsMessage,
    HealthProcessMessage,
    # 业务状态消息
    StatusStreamMessage,
    StatusHardwareMessage,
    # 响应消息
    ResponseMessage,
    LogErrorMessage,
)

__all__ = [
    # 核心组件
    'TopicManager',
    'MQTTPublisher',
    'MQTTMessageHandler',
    'MQTTMessageDispatcher',
    
    # 消息工厂和基类
    'MessageFactory',
    'CommandMessage',
    
    # 生命周期消息
    'LifecycleOnlineMessage',
    'LifecycleOfflineMessage',
    'LifecycleHeartbeatMessage',
    
    # 告警消息
    'AlarmIntrusionMessage',
    'AlarmSystemMessage',
    
    # 健康状态消息
    'HealthMetricsMessage',
    'HealthProcessMessage',
    
    # 业务状态消息
    'StatusStreamMessage',
    'StatusHardwareMessage',
    
    # 响应消息
    'ResponseMessage',
    'LogErrorMessage',
]
