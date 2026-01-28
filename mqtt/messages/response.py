"""
响应和日志消息模块
包含通用响应消息、错误日志消息
"""

from dataclasses import dataclass, field
from typing import Any, Dict

from .base import MQTTMessageBase


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
