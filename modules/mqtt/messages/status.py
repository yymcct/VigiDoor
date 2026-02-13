"""
业务状态消息模块
包含推流状态、硬件状态等业务相关的状态上报消息
"""

from dataclasses import dataclass, field
from typing import Any, Dict

from .base import MQTTMessageBase


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
