"""
设备抽象基类
定义输入设备和输出设备的统一接口
"""

from abc import ABC, abstractmethod
from typing import Any, Optional, Callable
from utils.logger import setup_logger

logger = setup_logger('device_base')


class DeviceBase(ABC):
    """
    设备抽象基类
    
    所有硬件设备的基类
    """
    
    def __init__(self, device_id: str, device_type: str, name: str):
        """
        初始化设备
        
        Args:
            device_id: 设备唯一标识
            device_type: 设备类型
            name: 设备名称
        """
        self.device_id = device_id
        self.device_type = device_type
        self.name = name
        self._initialized = False
    
    @abstractmethod
    def initialize(self) -> bool:
        """
        初始化设备硬件
        
        Returns:
            bool: 初始化成功返回 True
        """
        pass
    
    @abstractmethod
    def cleanup(self):
        """清理设备资源"""
        pass
    
    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return self._initialized
    
    def get_info(self) -> dict:
        """
        获取设备信息
        
        Returns:
            dict: 设备基本信息
        """
        return {
            'device_id': self.device_id,
            'device_type': self.device_type,
            'name': self.name,
            'initialized': self._initialized
        }


class InputDevice(DeviceBase):
    """
    输入设备基类
    
    用于按钮、传感器等输入设备
    """
    
    def __init__(self, device_id: str, device_type: str, name: str):
        super().__init__(device_id, device_type, name)
        self._callbacks = []
    
    @abstractmethod
    def read(self) -> Any:
        """
        读取设备状态
        
        Returns:
            Any: 设备当前状态数据
        """
        pass
    
    def register_callback(self, callback: Callable[[Any], None]):
        """
        注册事件回调
        
        Args:
            callback: 回调函数，参数为事件数据
        """
        self._callbacks.append(callback)
        logger.debug(f"{self.name} 注册回调: {callback.__name__}")
    
    def _trigger_callbacks(self, event_data: Any):
        """触发所有注册的回调"""
        for callback in self._callbacks:
            try:
                callback(event_data)
            except Exception as e:
                logger.error(f"{self.name} 回调执行失败: {e}")


class OutputDevice(DeviceBase):
    """
    输出设备基类
    
    用于 LED、蜂鸣器、继电器等输出设备
    """
    
    @abstractmethod
    def write(self, data: Any) -> bool:
        """
        写入数据到设备
        
        Args:
            data: 要写入的数据
            
        Returns:
            bool: 写入成功返回 True
        """
        pass
    
    @abstractmethod
    def update(self):
        """
        更新设备状态（用于动画等需要持续更新的设备）
        
        某些设备需要在主循环中持续调用此方法
        """
        pass
