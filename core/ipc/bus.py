"""
消息总线 - 统一的IPC入口
提供简洁的API供各进程使用
"""

import time
import uuid
import threading
from typing import Optional, Dict, Any
from .message import (
    IPCMessage,
    MessageType,
    MessagePriority,
    HeartbeatMessage,
    ShutdownMessage,
    AlarmMessage,
    CommandMessage,
    StatusMessage,
    create_message,
)
from .transport import Transport, MultiprocessingTransport
from .registry import ProcessName, ProcessRegistry


class MessageBus:
    """
    消息总线（主进程端）
    负责创建和管理所有进程的队列，并提供统一的消息分发
    """
    
    def __init__(self, max_queue_size: int = 1000):
        """
        初始化消息总线
        
        Args:
            max_queue_size: 每个队列的最大容量
        """
        self.transport = MultiprocessingTransport(max_queue_size)
        self._closed = False
        
        # 为所有注册的进程创建队列
        for process_name in ProcessName.all_processes():
            self.transport.create_queue(process_name)
    
    def send(self, target: str, message: IPCMessage) -> bool:
        """
        发送消息到目标进程
        
        Args:
            target: 目标进程名称
            message: 消息对象
            
        Returns:
            是否发送成功
        """
        if self._closed:
            return False
        return self.transport.send(target, message)
    
    def broadcast(self, message: IPCMessage, exclude: list = None) -> int:
        """
        广播消息到所有进程
        
        Args:
            message: 消息对象
            exclude: 排除的进程列表
            
        Returns:
            成功发送的进程数量
        """
        exclude = exclude or []
        success_count = 0
        
        for process_name in ProcessName.all_processes():
            if process_name not in exclude and process_name != ProcessName.SUPERVISOR:
                if self.send(process_name, message):
                    success_count += 1
        
        return success_count
    
    def get_client(self, process_name: str) -> 'IPCClient':
        """
        为子进程创建IPC客户端
        
        Args:
            process_name: 进程名称
            
        Returns:
            IPC客户端实例
        """
        return IPCClient(process_name, self.transport)
    
    def close(self) -> None:
        """关闭消息总线"""
        self._closed = True
        self.transport.close()
    
    def get_queue_sizes(self) -> Dict[str, int]:
        """获取所有队列的大小（用于监控）"""
        return self.transport.get_queue_sizes()


class IPCClient:
    """
    IPC客户端（子进程端）
    每个子进程持有一个客户端实例，用于发送和接收消息
    """
    
    def __init__(self, process_name: str, transport: Transport):
        """
        初始化IPC客户端
        
        Args:
            process_name: 当前进程名称
            transport: 传输层实例
        """
        self.process_name = process_name
        self.transport = transport
        self._pending_requests: Dict[str, threading.Event] = {}
        self._responses: Dict[str, IPCMessage] = {}
    
    def send(self, msg_type: MessageType, target: Optional[str] = None, 
             data: Any = None, priority: MessagePriority = MessagePriority.NORMAL) -> bool:
        """
        发送消息
        
        Args:
            msg_type: 消息类型
            target: 目标进程（None表示发送给supervisor）
            data: 消息数据
            priority: 消息优先级
            
        Returns:
            是否发送成功
        """
        target = target or ProcessName.SUPERVISOR
        
        message = IPCMessage(
            msg_type=msg_type,
            target=target,
            data=data,
            priority=priority,
        )
        
        return self.transport.send(target, message)
    
    def send_message(self, message: IPCMessage) -> bool:
        """
        发送消息对象
        
        Args:
            message: 消息对象
            
        Returns:
            是否发送成功
        """
        target = message.target or ProcessName.SUPERVISOR
        return self.transport.send(target, message)
    
    def send_heartbeat(self, uptime: int = 0, state: str = 'safe') -> bool:
        """发送心跳"""
        msg = HeartbeatMessage(uptime=uptime, state=state)
        return self.send_message(msg)
    
    def send_command(self, cmd_type: MessageType, target: str, cmd_data: dict = None) -> bool:
        """发送命令"""
        msg = CommandMessage(cmd_type=cmd_type, target=target, cmd_data=cmd_data)
        return self.send_message(msg)
    
    def send_status(self, status_type: MessageType, status_data: dict) -> bool:
        """发送状态"""
        msg = StatusMessage(status_type=status_type, status_data=status_data)
        return self.send_message(msg)
    
    def broadcast(self, message: IPCMessage, exclude_self: bool = True) -> int:
        """
        广播消息到所有进程
        
        Args:
            message: 消息对象
            exclude_self: 是否排除自己
            
        Returns:
            成功发送的进程数量
        """
        message.sender = self.process_name
        count = 0
        for process_name in self.transport.get_all_processes():
            if exclude_self and process_name == self.process_name:
                continue
            try:
                message.target = process_name
                if self.transport.send(process_name, message):
                    count += 1
            except:
                pass
        return count
    
    def receive(self, timeout: float = 1.0) -> Optional[IPCMessage]:
        """
        接收消息（阻塞）
        
        Args:
            timeout: 超时时间（秒）
            
        Returns:
            消息对象或None
        """
        return self.transport.receive(self.process_name, timeout=timeout)
    
    def request(self, target: str, msg_type: MessageType, 
                data: Any = None, timeout: float = 5.0) -> Optional[IPCMessage]:
        """
        发送请求并等待响应（同步模式）
        
        Args:
            target: 目标进程
            msg_type: 消息类型
            data: 消息数据
            timeout: 超时时间（秒）
            
        Returns:
            响应消息或None（超时）
        """
        # 生成唯一的请求ID
        request_id = str(uuid.uuid4())
        
        # 创建等待事件
        event = threading.Event()
        self._pending_requests[request_id] = event
        
        # 发送请求
        message = IPCMessage(
            msg_type=msg_type,
            target=target,
            data=data,
            message_id=request_id,
        )
        
        if not self.transport.send(target, message):
            del self._pending_requests[request_id]
            return None
        
        # 等待响应
        if event.wait(timeout):
            response = self._responses.pop(request_id, None)
            del self._pending_requests[request_id]
            return response
        else:
            # 超时
            del self._pending_requests[request_id]
            return None
    
    def _handle_response(self, response: IPCMessage) -> None:
        """
        处理响应消息（由消息循环调用）
        
        Args:
            response: 响应消息
        """
        request_id = response.message_id
        if request_id and request_id in self._pending_requests:
            self._responses[request_id] = response
            self._pending_requests[request_id].set()

