"""
下行指令消息模块
包含平台下发给设备的指令消息
"""

from dataclasses import dataclass, field
from typing import Any, Dict

from .base import MQTTMessageBase


@dataclass
class CommandMessage(MQTTMessageBase):
    """
    通用指令消息（用于解析平台下发的指令）

    JSON格式示例：
    {
        "device_id": "device123",
        "version": "1.0",
        "msg_id": "550e8400-e29b-41d4-a716-446655440000",
        "timestamp": 1719999999999,
        "data": {
            "action": "reboot",
            "params": {
                "delay": 5
            }
        }
    }
    """
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
