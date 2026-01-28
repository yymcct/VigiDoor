"""
帧队列管理模块
提供线程安全的帧队列，支持自动丢帧策略
"""

import queue
import threading
from typing import Optional, Tuple, Any
import numpy as np
from utils.logger import setup_logger

logger = setup_logger('frame_queue')


class FrameQueue:
    """
    线程安全的帧队列
    
    特性：
    - 线程安全
    - 自动丢帧（队列满时）
    - 统计信息
    """
    
    def __init__(self, maxsize: int = 5, name: str = "FrameQueue"):
        """
        初始化帧队列
        
        Args:
            maxsize: 最大队列长度
            name: 队列名称（用于日志）
        """
        self.queue = queue.Queue(maxsize=maxsize)
        self.name = name
        self.maxsize = maxsize
        
        # 统计信息
        self._lock = threading.Lock()
        self._put_count = 0
        self._get_count = 0
        self._dropped_count = 0
    
    def put(self, item: Tuple[np.ndarray, int, float], block: bool = False) -> bool:
        """
        放入帧（支持非阻塞模式，队列满时自动丢帧）
        
        Args:
            item: (frame, frame_id, timestamp) 元组
            block: 是否阻塞等待（默认 False，即非阻塞）
            
        Returns:
            bool: 成功放入返回 True，丢帧返回 False
        """
        try:
            if block:
                self.queue.put(item, block=True)
            else:
                self.queue.put_nowait(item)
            
            with self._lock:
                self._put_count += 1
            
            return True
            
        except queue.Full:
            with self._lock:
                self._dropped_count += 1
            
            if self._dropped_count % 10 == 0:
                logger.warning(
                    f"⚠️ {self.name} 队列已满，已丢弃 {self._dropped_count} 帧"
                )
            
            return False
    
    def get(self, timeout: Optional[float] = 1.0) -> Optional[Tuple[np.ndarray, int, float]]:
        """
        获取帧
        
        Args:
            timeout: 超时时间（秒），None 表示永久等待
            
        Returns:
            (frame, frame_id, timestamp) 或 None（超时）
        """
        try:
            item = self.queue.get(timeout=timeout)
            
            with self._lock:
                self._get_count += 1
            
            return item
            
        except queue.Empty:
            return None
    
    def clear(self):
        """清空队列"""
        cleared_count = 0
        
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
                cleared_count += 1
            except queue.Empty:
                break
        
        if cleared_count > 0:
            logger.info(f"{self.name} 清空了 {cleared_count} 帧")
    
    def size(self) -> int:
        """获取当前队列大小"""
        return self.queue.qsize()
    
    def is_full(self) -> bool:
        """检查队列是否已满"""
        return self.queue.full()
    
    def is_empty(self) -> bool:
        """检查队列是否为空"""
        return self.queue.empty()
    
    def get_stats(self) -> dict:
        """
        获取统计信息
        
        Returns:
            dict: 统计数据
        """
        with self._lock:
            return {
                'name': self.name,
                'current_size': self.size(),
                'max_size': self.maxsize,
                'put_count': self._put_count,
                'get_count': self._get_count,
                'dropped_count': self._dropped_count,
                'drop_rate': self._dropped_count / max(1, self._put_count + self._dropped_count)
            }
    
    def reset_stats(self):
        """重置统计信息"""
        with self._lock:
            self._put_count = 0
            self._get_count = 0
            self._dropped_count = 0
