"""
推流器抽象基类
（注：当前实现中，推流功能已整合到 FFmpegEncoder 中）
（此模块为未来扩展预留，如需要独立的推流控制可使用）
"""

from abc import ABC, abstractmethod


class StreamerBase(ABC):
    """
    推流器抽象基类
    
    为未来扩展独立推流控制预留接口
    """
    
    def __init__(self, stream_url: str):
        """
        初始化推流器
        
        Args:
            stream_url: 推流地址
        """
        self.stream_url = stream_url
        self._is_started = False
    
    @abstractmethod
    def start(self) -> bool:
        """
        启动推流
        
        Returns:
            bool: 启动成功返回 True
        """
        pass
    
    @abstractmethod
    def stop(self):
        """停止推流"""
        pass
    
    @abstractmethod
    def is_alive(self) -> bool:
        """
        检查推流是否正常
        
        Returns:
            bool: 正常推流返回 True
        """
        pass
    
    def is_started(self) -> bool:
        """检查是否已启动"""
        return self._is_started
    
    def get_url(self) -> str:
        """获取推流地址"""
        return self.stream_url
