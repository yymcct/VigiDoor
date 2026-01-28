"""
编码器抽象基类
定义统一的编码器接口
"""

from abc import ABC, abstractmethod
from typing import Optional
import numpy as np


class EncoderBase(ABC):
    """
    编码器抽象基类
    
    所有编码器必须实现这个接口
    """
    
    def __init__(self, width: int, height: int, fps: int, bitrate: str):
        """
        初始化编码器
        
        Args:
            width: 视频宽度
            height: 视频高度
            fps: 帧率
            bitrate: 码率（如 '2000k'）
        """
        self.width = width
        self.height = height
        self.fps = fps
        self.bitrate = bitrate
        self._is_initialized = False
    
    @abstractmethod
    def initialize(self, stream_url: str) -> bool:
        """
        初始化编码器
        
        Args:
            stream_url: 推流地址
            
        Returns:
            bool: 初始化成功返回 True
        """
        pass
    
    @abstractmethod
    def encode(self, frame: np.ndarray) -> bool:
        """
        编码一帧
        
        Args:
            frame: RGB 格式的图像帧
            
        Returns:
            bool: 编码成功返回 True
        """
        pass
    
    @abstractmethod
    def release(self):
        """释放编码器资源"""
        pass
    
    @abstractmethod
    def is_alive(self) -> bool:
        """
        检查编码器是否正常运行
        
        Returns:
            bool: 正常运行返回 True
        """
        pass
    
    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return self._is_initialized
    
    def get_info(self) -> dict:
        """
        获取编码器信息
        
        Returns:
            dict: 编码器配置信息
        """
        return {
            'width': self.width,
            'height': self.height,
            'fps': self.fps,
            'bitrate': self.bitrate,
            'initialized': self._is_initialized
        }
