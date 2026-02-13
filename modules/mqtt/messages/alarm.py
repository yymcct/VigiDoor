"""
告警消息模块
"""

from dataclasses import dataclass, field
from typing import Any, Dict

from .base import MQTTMessageBase


@dataclass
class AlarmIntrusionMessage(MQTTMessageBase):
    """告警消息"""
    data: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        super().__post_init__()
        
        defaults = {
            "alarm_type": "alarm_intrusion",  # person_detected/intrusion/detection
            "source": "camera_1",  # 设备或摄像头ID
            "confidence": 0.0,
            "intrusion_count": 0,  # 入侵目标数量
            "severity": "medium",  # low/medium/high/critical
            "snapshot_urls": [],  # 快照图片URL列表
            "video_urls": [],  # 视频回放URL列表
            "remark": ""  # 备注信息
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
