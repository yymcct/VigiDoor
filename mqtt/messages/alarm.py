"""
告警消息模块
包含 AI 视觉告警、音频异常告警、系统级严重告警等消息
"""

from dataclasses import dataclass, field
from typing import Any, Dict

from .base import MQTTMessageBase


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
