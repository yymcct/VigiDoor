"""
健康状态消息模块
包含系统健康指标、进程状态变更等消息
"""

from dataclasses import dataclass, field
from typing import Any, Dict

from .base import MQTTMessageBase


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
