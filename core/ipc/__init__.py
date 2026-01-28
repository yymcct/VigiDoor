"""
进程间通信(IPC)子系统
提供类型安全、可靠的消息传递机制

核心组件：
- Message: 消息定义和类型系统
- Registry: 进程注册表
- Transport: 传输层抽象
- MessageBus: 统一的消息总线入口
"""

from .message import (
    MessageType,
    MessagePriority,
    IPCMessage,
    HeartbeatMessage,
    ShutdownMessage,
    AlarmMessage,
    CommandMessage,
    StatusMessage,
    ResponseMessage,
)

from .registry import ProcessRegistry, ProcessInfo, ProcessName

from .transport import Transport, MultiprocessingTransport

from .bus import MessageBus, IPCClient

__all__ = [
    # 消息类型
    'MessageType',
    'MessagePriority',
    'IPCMessage',
    'HeartbeatMessage',
    'ShutdownMessage',
    'AlarmMessage',
    'CommandMessage',
    'StatusMessage',
    'ResponseMessage',
    
    # 进程管理
    'ProcessRegistry',
    'ProcessInfo',
    'ProcessName',
    
    # 传输层
    'Transport',
    'MultiprocessingTransport',
    
    # 主入口
    'MessageBus',
    'IPCClient',
]
