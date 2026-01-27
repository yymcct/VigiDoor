"""
进程间通信工具类
提供标准化的 IPC 消息格式和通信助手
"""

import multiprocessing as mp
import time
from typing import Any, Dict, Optional
import json


class IPCMessage:
    """标准 IPC 消息格式"""
    
    def __init__(self, msg_type: str, target: Optional[str] = None, data: Any = None):
        """
        创建 IPC 消息
        
        Args:
            msg_type: 消息类型（如 'heartbeat', 'anomaly_detected', 'mqtt_command'）
            target: 目标进程名称（None 表示发送给 supervisor）
            data: 消息数据
        """
        self.type = msg_type
        self.target = target
        self.data = data
        self.timestamp = time.time()
        try:
            self.from_process = mp.current_process().name
        except:
            self.from_process = "unknown"
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'type': self.type,
            'to': self.target,
            'data': self.data,
            'timestamp': self.timestamp,
            'from': self.from_process
        }


class IPCHelper:
    """IPC 辅助类 - 简化进程间通信"""
    
    def __init__(self, queue: mp.Queue, process_name: str):
        """
        初始化 IPC 助手
        
        Args:
            queue: 多进程消息队列
            process_name: 当前进程名称
        """
        self.queue = queue
        self.process_name = process_name
    
    def send(self, msg_type: str, target: Optional[str] = None, data: Any = None) -> bool:
        """
        发送消息
        
        Args:
            msg_type: 消息类型
            target: 目标进程（None 表示发送给 supervisor）
            data: 消息数据
            
        Returns:
            是否发送成功
        """
        try:
            msg = IPCMessage(msg_type, target, data)
            self.queue.put(msg.to_dict(), block=False)
            return True
        except Exception as e:
            # 队列满或其他异常，丢弃消息
            print(f"[{self.process_name}] 发送消息失败: {e}")
            return False
    
    def send_heartbeat(self) -> bool:
        """发送心跳"""
        return self.send('heartbeat', target='supervisor')
    
    def send_alarm(self, alarm_data: dict) -> bool:
        """发送告警"""
        return self.send('anomaly_detected', target='supervisor', data=alarm_data)
    
    def receive(self, timeout: float = 1.0) -> Optional[dict]:
        """
        接收消息（阻塞）
        
        Args:
            timeout: 超时时间（秒）
            
        Returns:
            消息字典或 None
        """
        try:
            msg = self.queue.get(timeout=timeout)
            # 只接收发给自己的消息
            if msg.get('to') == self.process_name or msg.get('to') is None:
                return msg
            else:
                # 不是发给自己的，放回队列
                self.queue.put(msg, block=False)
                return None
        except:
            return None


def format_message(msg_type: str, **kwargs) -> dict:
    """
    快速格式化消息
    
    Args:
        msg_type: 消息类型
        **kwargs: 其他字段
        
    Returns:
        消息字典
    """
    msg = IPCMessage(msg_type, kwargs.get('target'), kwargs.get('data'))
    return msg.to_dict()
