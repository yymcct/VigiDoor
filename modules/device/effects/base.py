"""
效果抽象基类
定义动画效果的统一接口
"""

from abc import ABC, abstractmethod


class EffectBase(ABC):
    """
    效果抽象基类
    
    用于 LED 动画、蜂鸣器节奏等效果
    """
    
    def __init__(self, name: str):
        """
        初始化效果
        
        Args:
            name: 效果名称
        """
        self.name = name
        self._is_running = False
    
    @abstractmethod
    def start(self):
        """启动效果"""
        pass
    
    @abstractmethod
    def update(self):
        """
        更新效果状态（每帧调用）
        
        返回是否需要继续更新
        """
        pass
    
    @abstractmethod
    def stop(self):
        """停止效果"""
        pass
    
    def is_running(self) -> bool:
        """检查效果是否正在运行"""
        return self._is_running
