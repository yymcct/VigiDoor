"""
MQTT 消息基类模块
定义所有消息的通用基础结构和序列化方法
"""

from dataclasses import dataclass, asdict
from typing import Optional
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
