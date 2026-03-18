"""
子进程上下文 - 封装子进程运行所需的所有依赖

每个子进程启动时由 process_wrapper 构建，通过单一对象传入进程 __init__

"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.ipc import IPCClient
    from utils.config import ConfigManager


@dataclass
class ProcessContext:
    """
    子进程运行上下文

    Attributes:
        ipc:          进程的 IPC 通信客户端，用于收发消息
        shared_state: 跨进程共享内存字典，子进程只读，写操作通过发消息给 Supervisor 完成
        config:       强类型配置管理器（ConfigManager 实例）
        process_name: 当前进程名称，与 ProcessName 注册表中的名称一致
    """
    ipc: 'IPCClient'
    shared_state: dict
    config: 'ConfigManager'
    process_name: str
