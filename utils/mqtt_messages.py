"""
MQTT 消息模型
使用 dataclass 定义标准化的消息结构，支持自动序列化和验证
"""

from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional
import uuid
import time
import json


@dataclass
class MQTTMessageBase:
    """
    MQTT 消息基类
    
    所有消息的统一格式，包含必填字段：
    - msg_id: 消息唯一ID
    - timestamp: Unix时间戳（毫秒）
    - device_id: 设备ID
    - version: 消息协议版本
    - data: 业务数据
    """
    device_id: str
    version: str = "1.0"
    msg_id: Optional[str] = None
    timestamp: Optional[int] = None
    
    def __post_init__(self):
        """自动生成 msg_id 和 timestamp"""
        if self.msg_id is None:
            self.msg_id = str(uuid.uuid4())
        if self.timestamp is None:
            self.timestamp = int(time.time() * 1000)  # 毫秒时间戳
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return asdict(self)
    
    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)
    
    @classmethod
    def from_json(cls, json_str: str):
        """从 JSON 字符串创建消息对象"""
        data = json.loads(json_str)
        return cls(**data)


# ==================== 上行消息（设备→平台）====================

# 2.1 设备生命周期管理

@dataclass
class LifecycleOnlineMessage(MQTTMessageBase):
    """设备上线消息"""
    data: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        super().__post_init__()
        # 默认数据结构
        if not self.data:
            self.data = {
                "device_name": "",
                "location": "",
                "firmware_version": "1.0.0",
                "ip_address": "",
                "mac_address": ""
            }


@dataclass
class LifecycleOfflineMessage(MQTTMessageBase):
    """设备离线消息"""
    data: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        super().__post_init__()
        if not self.data:
            self.data = {
                "reason": "unexpected",  # unexpected/normal/reboot
                "last_heartbeat": int(time.time() * 1000)
            }


@dataclass
class LifecycleHeartbeatMessage(MQTTMessageBase):
    """设备心跳消息"""
    data: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        super().__post_init__()
        if not self.data:
            self.data = {
                "uptime": 0,
                "global_state": "safe"  # safe/alert/alarm
            }


# 2.2 告警事件上报

@dataclass
class AlarmVisionMessage(MQTTMessageBase):
    """AI 视觉告警消息"""
    data: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        super().__post_init__()
        # 确保必填字段存在
        defaults = {
            "alarm_type": "person_detected",
            "confidence": 0.0,
            "object_count": 0,
            "severity": "medium",  # low/medium/high/critical
            "bounding_boxes": [],
            "snapshot_url": None
        }
        self.data = {**defaults, **self.data}


@dataclass
class AlarmAudioMessage(MQTTMessageBase):
    """音频异常告警消息"""
    data: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        super().__post_init__()
        defaults = {
            "alarm_type": "abnormal_sound",
            "anomaly_score": 0.0,
            "sound_category": None,
            "duration": 0.0,
            "audio_clip_url": None,
            "severity": "medium"
        }
        self.data = {**defaults, **self.data}


@dataclass
class AlarmSystemMessage(MQTTMessageBase):
    """系统级严重告警消息"""
    data: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        super().__post_init__()
        defaults = {
            "alarm_type": "system_error",
            "severity": "critical",
            "message": "",
            "process_name": None,
            "restart_attempts": 0
        }
        self.data = {**defaults, **self.data}


# 2.3 系统健康状态上报

@dataclass
class HealthMetricsMessage(MQTTMessageBase):
    """系统健康指标消息"""
    data: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        super().__post_init__()
        defaults = {
            "cpu_usage": 0.0,
            "memory_usage": 0.0,
            "disk_usage": 0.0,
            "temperature": 0.0,
            "uptime": 0,
            "network": {},
            "process_status": {}
        }
        self.data = {**defaults, **self.data}


@dataclass
class HealthProcessMessage(MQTTMessageBase):
    """进程状态变更消息"""
    data: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        super().__post_init__()
        defaults = {
            "process_name": "",
            "event": "started",  # started/stopped/restarted/crashed
            "pid": 0,
            "exit_code": None,
            "message": ""
        }
        self.data = {**defaults, **self.data}


# 2.4 业务状态上报

@dataclass
class StatusStreamMessage(MQTTMessageBase):
    """推流状态变更消息"""
    data: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        super().__post_init__()
        defaults = {
            "status": "stopped",  # started/stopped/failed
            "stream_url": None,
            "resolution": "1280x720",
            "fps": 25,
            "bitrate": "1000k",
            "codec": "h264"
        }
        self.data = {**defaults, **self.data}


@dataclass
class StatusHardwareMessage(MQTTMessageBase):
    """硬件状态变更消息"""
    data: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        super().__post_init__()
        defaults = {
            "led_strip": {},
            "camera": {},
            "microphone": {},
            "speaker": {}
        }
        self.data = {**defaults, **self.data}


# 2.5 日志上报

@dataclass
class LogErrorMessage(MQTTMessageBase):
    """错误日志消息"""
    data: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        super().__post_init__()
        defaults = {
            "level": "ERROR",
            "logger": "",
            "message": "",
            "traceback": None
        }
        self.data = {**defaults, **self.data}


# 2.6 响应消息

@dataclass
class ResponseMessage(MQTTMessageBase):
    """通用响应消息"""
    data: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        super().__post_init__()
        defaults = {
            "request_msg_id": "",
            "status": "success",  # success/failed/timeout
            "message": "",
            "error_code": None
        }
        self.data = {**defaults, **self.data}


# ==================== 下行消息（平台→设备）====================

@dataclass
class CommandMessage(MQTTMessageBase):
    """通用指令消息（用于解析平台下发的指令）"""
    data: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        super().__post_init__()
        if not self.data:
            self.data = {
                "action": "",
                "params": {}
            }
    
    def get_action(self) -> str:
        """获取指令动作"""
        return self.data.get('action', '')
    
    def get_params(self) -> dict:
        """获取指令参数"""
        return self.data.get('params', {})


# ==================== 消息工厂 ====================

class MessageFactory:
    """消息工厂 - 根据话题创建对应的消息对象"""
    
    # 话题关键字到消息类的映射
    MESSAGE_TYPE_MAP = {
        # 生命周期
        'lifecycle/online': LifecycleOnlineMessage,
        'lifecycle/offline': LifecycleOfflineMessage,
        'lifecycle/heartbeat': LifecycleHeartbeatMessage,
        
        # 告警
        'alarm/vision': AlarmVisionMessage,
        'alarm/audio': AlarmAudioMessage,
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
            ...     "vigidoor/up/RPI_001/alarm/vision",
            ...     "RPI_001",
            ...     {"alarm_type": "person_detected", "confidence": 0.95}
            ... )
            >>> isinstance(msg, AlarmVisionMessage)
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
            device_id = data.get('device_id', '')
            
            # 根据话题创建对应的消息对象
            for keyword, message_class in cls.MESSAGE_TYPE_MAP.items():
                if keyword in topic:
                    return message_class(**data)
            
            # 默认解析为基类
            return MQTTMessageBase(**data)
            
        except Exception as e:
            print(f"消息解析失败: {e}")
            return None
