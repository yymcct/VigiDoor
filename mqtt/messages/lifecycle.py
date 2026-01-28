"""
设备生命周期消息模块
包含设备上线、离线、心跳等生命周期管理消息
"""

from dataclasses import dataclass, field
from typing import Any, Dict
import time

from .base import MQTTMessageBase


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
