"""
设备管理器
统一管理所有 IO 设备
"""

from typing import Dict, Optional, List
from .devices.base import DeviceBase, InputDevice, OutputDevice
from utils.logger import setup_logger

logger = setup_logger('device_manager')


class DeviceManager:
    """
    设备管理器
    
    负责：
    1. 设备注册和生命周期管理
    2. 统一的设备访问接口
    3. 批量设备操作
    """
    
    def __init__(self):
        """初始化设备管理器"""
        self._devices: Dict[str, DeviceBase] = {}
        self._input_devices: Dict[str, InputDevice] = {}
        self._output_devices: Dict[str, OutputDevice] = {}
        
        logger.info("设备管理器初始化完成")
    
    def register_device(self, device: DeviceBase) -> bool:
        """
        注册设备
        
        Args:
            device: 设备对象
            
        Returns:
            是否注册成功
        """
        try:
            device_id = device.device_id
            
            if device_id in self._devices:
                logger.warning(f"设备已存在: {device_id}")
                return False
            
            # 初始化设备
            if not device.initialize():
                logger.error(f"设备初始化失败: {device_id}")
                return False
            
            # 注册到对应的字典
            self._devices[device_id] = device
            
            if isinstance(device, InputDevice):
                self._input_devices[device_id] = device
                logger.info(f"✅ 输入设备注册成功: {device.name}")
            elif isinstance(device, OutputDevice):
                self._output_devices[device_id] = device
                logger.info(f"✅ 输出设备注册成功: {device.name}")
            else:
                logger.info(f"✅ 设备注册成功: {device.name}")
            
            return True
            
        except Exception as e:
            logger.error(f"设备注册失败: {e}")
            return False
    
    def unregister_device(self, device_id: str) -> bool:
        """
        注销设备
        
        Args:
            device_id: 设备 ID
            
        Returns:
            是否注销成功
        """
        try:
            if device_id not in self._devices:
                logger.warning(f"设备不存在: {device_id}")
                return False
            
            device = self._devices[device_id]
            
            # 清理设备资源
            device.cleanup()
            
            # 从字典中移除
            del self._devices[device_id]
            if device_id in self._input_devices:
                del self._input_devices[device_id]
            if device_id in self._output_devices:
                del self._output_devices[device_id]
            
            logger.info(f"设备已注销: {device.name}")
            return True
            
        except Exception as e:
            logger.error(f"设备注销失败: {e}")
            return False
    
    def get_device(self, device_id: str) -> Optional[DeviceBase]:
        """
        获取设备对象
        
        Args:
            device_id: 设备 ID
            
        Returns:
            设备对象，如果不存在则返回 None
        """
        return self._devices.get(device_id)
    
    def get_input_device(self, device_id: str) -> Optional[InputDevice]:
        """
        获取输入设备对象
        
        Args:
            device_id: 设备 ID
            
        Returns:
            输入设备对象，如果不存在则返回 None
        """
        return self._input_devices.get(device_id)
    
    def get_output_device(self, device_id: str) -> Optional[OutputDevice]:
        """
        获取输出设备对象
        
        Args:
            device_id: 设备 ID
            
        Returns:
            输出设备对象，如果不存在则返回 None
        """
        return self._output_devices.get(device_id)
    
    def get_all_devices(self) -> List[DeviceBase]:
        """
        获取所有设备
        
        Returns:
            设备列表
        """
        return list(self._devices.values())
    
    def get_all_input_devices(self) -> List[InputDevice]:
        """
        获取所有输入设备
        
        Returns:
            输入设备列表
        """
        return list(self._input_devices.values())
    
    def get_all_output_devices(self) -> List[OutputDevice]:
        """
        获取所有输出设备
        
        Returns:
            输出设备列表
        """
        return list(self._output_devices.values())
    
    def update_all_outputs(self):
        """
        更新所有输出设备
        
        用于驱动需要持续更新的设备（如 LED 动画）
        """
        for device in self._output_devices.values():
            device.update()
    
    def cleanup_all(self):
        """清理所有设备"""
        logger.info("开始清理所有设备")
        
        for device_id in list(self._devices.keys()):
            self.unregister_device(device_id)
        
        logger.info("所有设备已清理")
    
    def get_device_info(self, device_id: str) -> Optional[Dict]:
        """
        获取设备信息
        
        Args:
            device_id: 设备 ID
            
        Returns:
            设备信息字典，如果不存在则返回 None
        """
        device = self._devices.get(device_id)
        if device:
            return device.get_info()
        return None
    
    def get_all_device_info(self) -> List[Dict]:
        """
        获取所有设备信息
        
        Returns:
            设备信息列表
        """
        return [device.get_info() for device in self._devices.values()]
