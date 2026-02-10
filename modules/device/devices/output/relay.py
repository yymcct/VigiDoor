"""
继电器输出设备实现
用于控制高电压/大电流设备
"""

import time
from typing import Dict, Any, Optional
from gpiozero import DigitalOutputDevice
from ..base import OutputDevice
from ...effects.base import EffectBase
from utils.logger import setup_logger

logger = setup_logger('relay')


class RelayDevice(OutputDevice):
    """
    继电器设备
    
    用于控制：
    - 电灯
    - 电机
    - 电磁锁
    - 其他高电压设备
    """
    
    def __init__(self, pin: int, normally_open: bool = True, 
                 name: str = None, simulate: bool = False):
        """
        初始化继电器
        
        Args:
            pin: GPIO 引脚号
            normally_open: 是否为常开型（True=常开NO，False=常闭NC）
            name: 继电器控制的设备名称
            simulate: 是否使用模拟模式
        """
        device_name = name or f"Relay (GPIO{pin})"
        super().__init__(
            device_id=f"relay_{pin}",
            device_type="relay",
            name=device_name
        )
        
        self.pin = pin
        self.normally_open = normally_open
        self.simulate = simulate
        
        self._device: Optional[DigitalOutputDevice] = None
        self._is_on = False
        self._current_effect: Optional[EffectBase] = None
    
    def initialize(self) -> bool:
        """
        初始化继电器
        
        Returns:
            是否初始化成功
        """
        try:
            if self.simulate:
                # 模拟模式
                logger.info(f"✅ 继电器初始化成功（模拟模式）")
                logger.info(f"  引脚: GPIO {self.pin}")
                logger.info(f"  类型: {'常开(NO)' if self.normally_open else '常闭(NC)'}")
                logger.info(f"  控制: {self.name}")
                self._initialized = True
                return True
            
            # 尝试初始化真实硬件
            try:
                # 使用 gpiozero 的 DigitalOutputDevice
                # active_high=True 表示常开(NO)，False 表示常闭(NC)
                self._device = DigitalOutputDevice(
                    self.pin,
                    active_high=self.normally_open,
                    initial_value=False
                )
                
                logger.info("✅ 继电器初始化成功")
                logger.info(f"  引脚: GPIO {self.pin}")
                logger.info(f"  类型: {'常开(NO)' if self.normally_open else '常闭(NC)'}")
                logger.info(f"  控制: {self.name}")
                
                self._initialized = True
                return True
                
            except Exception as hw_error:
                logger.warning(f"硬件初始化失败: {hw_error}，切换到模拟模式")
                self.simulate = True
                self._initialized = True
                return True
                
        except Exception as e:
            logger.error(f"继电器初始化失败: {e}")
            self._initialized = False
            return False
    
    def cleanup(self):
        """清理资源"""
        try:
            # 停止效果
            if self._current_effect:
                self._current_effect.stop()
            
            # 关闭继电器
            if self._device:
                self._device.off()
                self._device.close()
            
            logger.info("继电器已清理")
            
        except Exception as e:
            logger.error(f"继电器清理失败: {e}")
    
    def write(self, data: bool) -> bool:
        """
        控制继电器开关
        
        Args:
            data: True=开启，False=关闭
            
        Returns:
            是否设置成功
        """
        if not self._initialized:
            return False
        
        try:
            self._is_on = data
            
            # 停止当前效果（手动控制时）
            if self._current_effect and self._current_effect.is_running():
                self._current_effect.stop()
                self._current_effect = None
            
            if self.simulate:
                # 模拟模式
                logger.info(f"  [模拟] {self.name}: {'开启' if data else '关闭'}")
                return True
            
            # 真实硬件
            if self._device:
                # gpiozero 会根据 active_high 参数自动处理逻辑
                if data:
                    self._device.on()
                else:
                    self._device.off()
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"控制继电器失败: {e}")
            return False
    
    def turn_on(self) -> bool:
        """
        开启继电器
        
        Returns:
            是否成功
        """
        return self.write(True)
    
    def turn_off(self) -> bool:
        """
        关闭继电器
        
        Returns:
            是否成功
        """
        return self.write(False)
    
    def toggle(self) -> bool:
        """
        切换继电器状态
        
        Returns:
            是否成功
        """
        return self.write(not self._is_on)
    
    def is_on(self) -> bool:
        """
        检查继电器是否开启
        
        Returns:
            是否开启
        """
        return self._is_on
    
    def pulse(self, duration: float = 0.5):
        """
        脉冲控制（开启一段时间后自动关闭）
        
        Args:
            duration: 持续时间（秒）
        """
        self.turn_on()
        time.sleep(duration)
        self.turn_off()
    
    def set_effect(self, effect: EffectBase):
        """
        设置效果（如闪烁）
        
        Args:
            effect: 效果对象
        """
        # 停止当前效果
        if self._current_effect and self._current_effect.is_running():
            self._current_effect.stop()
        
        # 启动新效果
        self._current_effect = effect
        self._current_effect.start()
    
    def stop_effect(self):
        """停止当前效果"""
        if self._current_effect:
            self._current_effect.stop()
            self._current_effect = None
            # 关闭继电器
            self._apply_state(False)
    
    def update(self):
        """
        更新状态（用于驱动效果动画）
        """
        if not self._initialized or not self._current_effect:
            return
        
        try:
            if self._current_effect.is_running():
                # 获取效果当前帧的状态
                state = self._current_effect.update()
                if state is not None:
                    self._apply_state(state)
        
        except Exception as e:
            logger.error(f"更新继电器效果失败: {e}")
    
    def _apply_state(self, state: bool):
        """
        内部方法：直接应用状态到硬件（不影响效果）
        
        Args:
            state: True=开启，False=关闭
        """
        self._is_on = state
        
        if self.simulate:
            # 模拟模式
            logger.debug(f"  [模拟] {self.name}: {'开启' if state else '关闭'}")
            return
        
        # 真实硬件
        if self._device:
            if state:
                self._device.on()
            else:
                self._device.off()
    
    def get_info(self) -> Dict[str, Any]:
        """
        获取设备信息
        
        Returns:
            设备信息字典
        """
        info = super().get_info()
        info.update({
            'pin': self.pin,
            'normally_open': self.normally_open,
            'simulate': self.simulate,
            'is_on': self._is_on,
            'current_effect': self._current_effect.name if self._current_effect else None
        })
        return info
