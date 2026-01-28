"""
IPC消息定义和类型系统
提供类型安全的消息定义，支持序列化和验证
"""

import time
import json
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Optional
import multiprocessing as mp


class MessageType(str, Enum):
    """消息类型枚举"""
    
    # ========== 生命周期消息 ==========
    HEARTBEAT = "heartbeat"
    SHUTDOWN = "shutdown"
    PROCESS_STARTED = "process_started"
    PROCESS_STOPPED = "process_stopped"
    
    # ========== 告警消息 ==========
    ALARM_VISION = "alarm_vision"           # 视觉告警（检测到异常）
    ALARM_AUDIO = "alarm_audio"             # 音频告警（异常声音）
    ALARM_SYSTEM = "alarm_system"           # 系统告警（严重错误）
    ANOMALY_DETECTED = "anomaly_detected"   # 兼容旧代码
    AUDIO_ANOMALY = "audio_anomaly"         # 兼容旧代码
    
    # ========== 帧数据消息 ==========
    FRAME_READY = "frame_ready"             # 新帧就绪通知
    
    # ========== 命令消息 ==========
    CMD_START_STREAM = "cmd_start_stream"
    CMD_STOP_STREAM = "cmd_stop_stream"
    CMD_SET_LIGHT = "cmd_set_light"
    CMD_PLAY_AUDIO = "cmd_play_audio"
    CMD_TAKE_SNAPSHOT = "cmd_take_snapshot"
    
    # ========== 状态上报 ==========
    STATUS_STREAM = "status_stream"
    STATUS_HARDWARE = "status_hardware"
    STATUS_HEALTH = "status_health"
    STATUS_PROCESS = "status_process"
    
    # ========== MQTT相关 ==========
    MQTT_COMMAND = "mqtt_command"           # 来自平台的指令
    REPORT_ALARM = "report_alarm"           # 上报告警
    REPORT_HEALTH = "report_health"         # 上报健康状态
    
    # ========== 请求-响应 ==========
    REQUEST = "request"
    RESPONSE = "response"
    
    # ========== 兼容旧代码 ==========
    SET_LIGHT = "set_light"
    PLAY_AUDIO = "play_audio"
    STREAM_STATUS_CHANGED = "stream_status_changed"
    HARDWARE_STATUS_CHANGED = "hardware_status_changed"
    PROCESS_STATUS_CHANGED = "process_status_changed"
    CRITICAL_ALARM = "critical_alarm"


class MessagePriority(int, Enum):
    """消息优先级"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3  # 如 SHUTDOWN, CRITICAL_ALARM


@dataclass
class IPCMessage:
    """
    IPC消息基类
    所有消息都继承此类，提供统一的序列化和验证
    """
    
    msg_type: MessageType
    target: Optional[str] = None        # 目标进程（None表示发给supervisor）
    data: Optional[Dict[str, Any]] = None
    priority: MessagePriority = MessagePriority.NORMAL
    
    # 自动填充字段
    timestamp: float = field(default_factory=time.time)
    sender: str = field(default_factory=lambda: mp.current_process().name)
    message_id: Optional[str] = None    # 用于请求-响应匹配
    
    def to_dict(self) -> dict:
        """转换为字典"""
        result = {
            'type': self.msg_type.value if isinstance(self.msg_type, MessageType) else self.msg_type,
            'to': self.target,
            'data': self.data or {},
            'priority': self.priority.value if isinstance(self.priority, MessagePriority) else self.priority,
            'timestamp': self.timestamp,
            'from': self.sender,
        }
        if self.message_id:
            result['message_id'] = self.message_id
        return result
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_dict(cls, data: dict) -> 'IPCMessage':
        """从字典创建消息"""
        msg_type_str = data.get('type')
        try:
            msg_type = MessageType(msg_type_str)
        except ValueError:
            msg_type = msg_type_str  # 保持字符串，兼容未定义的类型
        
        return cls(
            msg_type=msg_type,
            target=data.get('to'),
            data=data.get('data'),
            priority=MessagePriority(data.get('priority', MessagePriority.NORMAL)),
            timestamp=data.get('timestamp', time.time()),
            sender=data.get('from', 'unknown'),
            message_id=data.get('message_id'),
        )
    
    def validate(self) -> bool:
        """验证消息格式"""
        if not self.msg_type:
            return False
        if not self.sender:
            return False
        return True


# ========== 具体消息类型 ==========

@dataclass
class HeartbeatMessage(IPCMessage):
    """心跳消息"""
    
    def __init__(self, uptime: int = 0, state: str = 'safe', **kwargs):
        super().__init__(
            msg_type=MessageType.HEARTBEAT,
            target='supervisor',
            data={'uptime': uptime, 'state': state},
            **kwargs
        )


@dataclass
class ShutdownMessage(IPCMessage):
    """关闭消息"""
    
    def __init__(self, target: str, reason: str = '', **kwargs):
        super().__init__(
            msg_type=MessageType.SHUTDOWN,
            target=target,
            data={'reason': reason},
            priority=MessagePriority.CRITICAL,
            **kwargs
        )


@dataclass
class AlarmMessage(IPCMessage):
    """告警消息"""
    
    def __init__(self, alarm_type: MessageType, alarm_data: dict, **kwargs):
        super().__init__(
            msg_type=alarm_type,
            target='supervisor',
            data=alarm_data,
            priority=MessagePriority.HIGH,
            **kwargs
        )


@dataclass
class CommandMessage(IPCMessage):
    """命令消息"""
    
    def __init__(self, cmd_type: MessageType, target: str, cmd_data: dict = None, **kwargs):
        super().__init__(
            msg_type=cmd_type,
            target=target,
            data=cmd_data or {},
            **kwargs
        )


@dataclass
class FrameReadyMessage(IPCMessage):
    """帧就绪消息"""
    
    def __init__(self, frame_id: int, timestamp: float, width: int, height: int, target: str = 'stream_manager', **kwargs):
        super().__init__(
            msg_type=MessageType.FRAME_READY,
            target=target,
            data={
                'frame_id': frame_id,
                'timestamp': timestamp,
                'width': width,
                'height': height
            },
            **kwargs
        )


@dataclass
class StatusMessage(IPCMessage):
    """状态消息"""
    
    def __init__(self, status_type: MessageType, status_data: dict, **kwargs):
        super().__init__(
            msg_type=status_type,
            target='supervisor',
            data=status_data,
            **kwargs
        )


@dataclass
class ResponseMessage(IPCMessage):
    """响应消息"""
    
    def __init__(self, request_id: str, target: str, response_data: dict = None, **kwargs):
        super().__init__(
            msg_type=MessageType.RESPONSE,
            target=target,
            data=response_data or {},
            message_id=request_id,
            **kwargs
        )


# ========== 快捷工具函数 ==========

def create_message(msg_type: str, target: Optional[str] = None, data: Any = None, **kwargs) -> IPCMessage:
    """
    快速创建消息的工厂函数
    兼容旧代码的dict构造方式
    """
    try:
        msg_type_enum = MessageType(msg_type)
    except ValueError:
        msg_type_enum = msg_type
    
    return IPCMessage(
        msg_type=msg_type_enum,
        target=target,
        data=data,
        **kwargs
    )
