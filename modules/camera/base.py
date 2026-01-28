"""
摄像头驱动抽象基类
定义统一的驱动接口，方便扩展不同类型的摄像头
"""

from abc import ABC, abstractmethod
from typing import Optional, Tuple
import numpy as np


class CameraDriverBase(ABC):
    """
    摄像头驱动抽象基类
    
    所有摄像头驱动必须实现这个接口，提供统一的访问方式
    """
    
    def __init__(self, width: int, height: int, target_fps: int, format: str):
        """
        初始化驱动基本参数
        
        Args:
            width: 图像宽度
            height: 图像高度
            target_fps: 目标帧率
            format: 像素格式（如 'RGB888'）
        """
        self.width = width
        self.height = height
        self.target_fps = target_fps
        self.format = format
        self._is_initialized = False
    
    @abstractmethod
    def initialize(self) -> bool:
        """
        初始化摄像头硬件/资源
        
        Returns:
            bool: 初始化成功返回 True，否则返回 False
        """
        pass
    
    @abstractmethod
    def capture_frame(self) -> Optional[np.ndarray]:
        """
        捕获一帧图像
        
        Returns:
            np.ndarray: RGB 格式的图像数据 (H, W, 3)，失败返回 None
        """
        pass
    
    @abstractmethod
    def release(self):
        """
        释放摄像头资源
        """
        pass
    
    @abstractmethod
    def get_info(self) -> dict:
        """
        获取驱动信息
        
        Returns:
            dict: 包含驱动类型、版本等信息
        """
        pass
    
    def is_initialized(self) -> bool:
        """
        检查是否已初始化
        
        Returns:
            bool: 已初始化返回 True
        """
        return self._is_initialized
    
    def get_resolution(self) -> Tuple[int, int]:
        """
        获取分辨率
        
        Returns:
            Tuple[int, int]: (width, height)
        """
        return (self.width, self.height)
