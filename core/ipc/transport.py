"""
传输层抽象
提供不同传输方式的统一接口，支持未来扩展到ZeroMQ等
"""

import queue
import multiprocessing as mp
from abc import ABC, abstractmethod
from typing import Optional, Dict
from .message import IPCMessage


class Transport(ABC):
    """
    传输层抽象基类
    未来可以实现 ZeroMQTransport, RedisTransport 等
    """
    
    @abstractmethod
    def send(self, target: str, message: IPCMessage) -> bool:
        """
        发送消息到目标进程
        
        Args:
            target: 目标进程名称
            message: 消息对象
            
        Returns:
            是否发送成功
        """
        pass
    
    @abstractmethod
    def receive(self, process_name: str, timeout: float = 1.0) -> Optional[IPCMessage]:
        """
        从自己的队列接收消息
        
        Args:
            process_name: 当前进程名称
            timeout: 超时时间（秒）
            
        Returns:
            消息对象或None
        """
        pass
    
    @abstractmethod
    def create_queue(self, process_name: str) -> None:
        """为进程创建消息队列"""
        pass
    
    @abstractmethod
    def close(self) -> None:
        """关闭传输层"""
        pass
    
    @abstractmethod
    def get_all_processes(self) -> list:
        """获取所有已注册的进程名称"""
        pass


class MultiprocessingTransport(Transport):
    """
    基于 multiprocessing.Queue 的传输层实现
    每个进程有独立的接收队列，避免消息竞争
    """
    
    def __init__(self, max_queue_size: int = 1000):
        """
        初始化传输层
        
        Args:
            max_queue_size: 每个队列的最大容量
        """
        self.max_queue_size = max_queue_size
        self.queues: Dict[str, mp.Queue] = {}
        self._closed = False
    
    def create_queue(self, process_name: str) -> None:
        """为进程创建消息队列"""
        if process_name not in self.queues:
            self.queues[process_name] = mp.Queue(maxsize=self.max_queue_size)
    
    def send(self, target: str, message: IPCMessage) -> bool:
        """
        发送消息到目标进程的队列
        
        Args:
            target: 目标进程名称
            message: 消息对象
            
        Returns:
            是否发送成功
        """
        if self._closed:
            return False
        
        # 确保目标队列存在
        if target not in self.queues:
            print(f"[Transport] 警告: 目标进程 {target} 的队列不存在，尝试创建")
            self.create_queue(target)
        
        try:
            # 转换为字典后发送
            msg_dict = message.to_dict()
            self.queues[target].put(msg_dict, block=False)
            return True
        except queue.Full:
            print(f"[Transport] 错误: 进程 {target} 的队列已满，消息被丢弃")
            return False
        except Exception as e:
            print(f"[Transport] 发送消息失败: {e}")
            return False
    
    def receive(self, process_name: str, timeout: float = 1.0) -> Optional[IPCMessage]:
        """
        从自己的队列接收消息
        
        Args:
            process_name: 当前进程名称
            timeout: 超时时间（秒）
            
        Returns:
            消息对象或None
        """
        if self._closed:
            return None
        
        # 确保自己的队列存在
        if process_name not in self.queues:
            self.create_queue(process_name)
        
        try:
            msg_dict = self.queues[process_name].get(timeout=timeout)
            # 从字典恢复为消息对象
            return IPCMessage.from_dict(msg_dict)
        except queue.Empty:
            return None
        except Exception as e:
            print(f"[Transport] 接收消息失败: {e}")
            return None
    
    def get_queue(self, process_name: str) -> Optional[mp.Queue]:
        """获取指定进程的队列（用于传递给子进程）"""
        return self.queues.get(process_name)
    
    def close(self) -> None:
        """关闭所有队列"""
        self._closed = True
        # multiprocessing.Queue 会自动清理，不需要显式关闭
        self.queues.clear()
    
    def get_all_processes(self) -> list:
        """获取所有已注册的进程名称"""
        return list(self.queues.keys())
    
    def get_queue_sizes(self) -> Dict[str, int]:
        """获取所有队列的大小（用于监控）"""
        sizes = {}
        for name, q in self.queues.items():
            try:
                sizes[name] = q.qsize()
            except:
                sizes[name] = -1  # 某些平台不支持qsize
        return sizes
