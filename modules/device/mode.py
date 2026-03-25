"""
设备模式管理模块
定义设备工作模式和模式管理器
"""

from enum import Enum
from utils.logger import setup_logger

logger = setup_logger('device_mode')


class DeviceMode(Enum):
    """设备工作模式"""
    DAILY = "daily"    # 撤防 / 日常经营
    GUARD = "guard"    # 布防 / 守卫中
    SAFE = "safe"      # 向后兼容别名（等同于 GUARD）
    ALERT = "alert"    # 布防 / 警戒状态
    ALARM = "alarm"    # 布防 / 异常告警


class ModeManager:
    """
    模式管理器
    
    负责管理系统工作模式，协调各设备状态
    """
    
    def __init__(self, initial_mode: DeviceMode = DeviceMode.SAFE):
        """
        初始化模式管理器
        
        Args:
            initial_mode: 初始模式
        """
        self._current_mode = initial_mode
        self._mode_callbacks = []
        
        logger.info(f"模式管理器初始化，当前模式: {initial_mode.value}")
    
    @property
    def current_mode(self) -> DeviceMode:
        """获取当前模式"""
        return self._current_mode
    
    def get_mode(self) -> DeviceMode:
        """
        获取当前模式
        
        Returns:
            当前工作模式
        """
        return self._current_mode
    
    def set_mode(self, mode: DeviceMode) -> bool:
        """
        设置工作模式
        
        Args:
            mode: 目标模式
            
        Returns:
            bool: 设置成功返回 True
        """
        if mode == self._current_mode:
            logger.debug(f"模式未变化: {mode.value}")
            return False
        
        old_mode = self._current_mode
        self._current_mode = mode
        
        logger.info(f"💡 模式切换: {old_mode.value} → {mode.value}")
        
        # 触发回调
        self._trigger_callbacks(old_mode, mode)
        
        return True
    
    def register_callback(self, callback):
        """
        注册模式变化回调
        
        Args:
            callback: 回调函数，签名为 callback(old_mode, new_mode)
        """
        self._mode_callbacks.append(callback)
    
    def add_callback(self, callback):
        """
        添加模式变化回调（register_callback 的别名）
        
        Args:
            callback: 回调函数，签名为 callback(old_mode, new_mode)
        """
        self.register_callback(callback)
    
    def _trigger_callbacks(self, old_mode: DeviceMode, new_mode: DeviceMode):
        """触发所有注册的回调"""
        for callback in self._mode_callbacks:
            try:
                callback(old_mode, new_mode)
            except Exception as e:
                logger.error(f"模式回调执行失败: {e}")
    
    def is_safe(self) -> bool:
        """是否处于安全模式"""
        return self._current_mode == DeviceMode.SAFE
    
    def is_alert(self) -> bool:
        """是否处于警戒模式"""
        return self._current_mode == DeviceMode.ALERT
    
    def is_alarm(self) -> bool:
        """是否处于报警模式"""
        return self._current_mode == DeviceMode.ALARM
