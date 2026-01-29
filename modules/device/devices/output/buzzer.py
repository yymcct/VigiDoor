"""
蜂鸣器输出设备实现
支持有源和无源蜂鸣器
"""

import time
from typing import Optional, Dict, Any
from ..base import OutputDevice
from ...effects.base import EffectBase
from utils.logger import setup_logger

logger = setup_logger('buzzer')


class BuzzerDevice(OutputDevice):
    """
    蜂鸣器设备
    
    支持：
    - 有源蜂鸣器（简单开关）
    - 无源蜂鸣器（PWM 频率控制）
    - 音效系统集成
    """
    
    def __init__(self, pin: int, pwm_enabled: bool = False, 
                 default_frequency: int = 2000, simulate: bool = False):
        """
        初始化蜂鸣器
        
        Args:
            pin: GPIO 引脚号
            pwm_enabled: 是否启用 PWM（无源蜂鸣器需要）
            default_frequency: 默认频率（Hz）
            simulate: 是否使用模拟模式
        """
        super().__init__(
            device_id=f"buzzer_{pin}",
            device_type="buzzer",
            name=f"Buzzer (GPIO{pin})"
        )
        
        self.pin = pin
        self.pwm_enabled = pwm_enabled
        self.default_frequency = default_frequency
        self.simulate = simulate
        
        self._gpio = None
        self._pwm = None
        self._is_active = False
        self._current_effect: Optional[EffectBase] = None
    
    def initialize(self) -> bool:
        """
        初始化蜂鸣器
        
        Returns:
            是否初始化成功
        """
        try:
            if self.simulate:
                # 模拟模式
                logger.info(f"✅ 蜂鸣器初始化成功（模拟模式）")
                logger.info(f"  引脚: GPIO {self.pin}")
                logger.info(f"  类型: {'无源(PWM)' if self.pwm_enabled else '有源'}")
                self._initialized = True
                return True
            
            # 尝试初始化真实硬件
            try:
                import RPi.GPIO as GPIO
                
                GPIO.setmode(GPIO.BCM)
                GPIO.setup(self.pin, GPIO.OUT)
                
                self._gpio = GPIO
                
                # 如果启用 PWM
                if self.pwm_enabled:
                    self._pwm = GPIO.PWM(self.pin, self.default_frequency)
                    self._pwm.start(0)  # 初始占空比为 0（关闭）
                else:
                    GPIO.output(self.pin, GPIO.LOW)
                
                logger.info("✅ 蜂鸣器初始化成功")
                logger.info(f"  引脚: GPIO {self.pin}")
                logger.info(f"  类型: {'无源(PWM)' if self.pwm_enabled else '有源'}")
                
                self._initialized = True
                return True
                
            except ImportError:
                logger.warning("RPi.GPIO 库未安装，切换到模拟模式")
                self.simulate = True
                self._initialized = True
                return True
                
        except Exception as e:
            logger.error(f"蜂鸣器初始化失败: {e}")
            self._initialized = False
            return False
    
    def cleanup(self):
        """清理资源"""
        try:
            # 关闭蜂鸣器
            self.write(False)
            
            if self._pwm:
                self._pwm.stop()
            
            if self._gpio:
                self._gpio.cleanup(self.pin)
            
            logger.info("蜂鸣器已清理")
            
        except Exception as e:
            logger.error(f"蜂鸣器清理失败: {e}")
    
    def write(self, data: bool) -> bool:
        """
        控制蜂鸣器开关
        
        Args:
            data: True=开启，False=关闭
            
        Returns:
            是否设置成功
        """
        if not self._initialized:
            return False
        
        try:
            self._is_active = data
            
            # 停止当前效果
            if self._current_effect and self._current_effect.is_running():
                self._current_effect.stop()
                self._current_effect = None
            
            if self.simulate:
                # 模拟模式
                logger.info(f"  [模拟] 蜂鸣器: {'开启' if data else '关闭'}")
                return True
            
            # 真实硬件
            if self._gpio:
                if self.pwm_enabled and self._pwm:
                    if data:
                        self._pwm.ChangeDutyCycle(50)  # 50% 占空比
                    else:
                        self._pwm.ChangeDutyCycle(0)
                else:
                    self._gpio.output(self.pin, self._gpio.HIGH if data else self._gpio.LOW)
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"控制蜂鸣器失败: {e}")
            return False
    
    def beep(self, duration: float = 0.1):
        """
        发出短促的蜂鸣声
        
        Args:
            duration: 持续时间（秒）
        """
        self.write(True)
        time.sleep(duration)
        self.write(False)
    
    def set_frequency(self, frequency: int) -> bool:
        """
        设置蜂鸣器频率（仅 PWM 模式）
        
        Args:
            frequency: 频率（Hz）
            
        Returns:
            是否设置成功
        """
        if not self.pwm_enabled or not self._pwm:
            logger.warning("蜂鸣器未启用 PWM 模式")
            return False
        
        try:
            if self.simulate:
                logger.info(f"  [模拟] 设置频率: {frequency} Hz")
                return True
            
            self._pwm.ChangeFrequency(frequency)
            return True
            
        except Exception as e:
            logger.error(f"设置频率失败: {e}")
            return False
    
    def update(self):
        """
        更新效果（需要在主循环中定期调用）
        """
        if not self._initialized or not self._current_effect:
            return
        
        try:
            if self._current_effect.is_running():
                # 获取效果当前状态
                state = self._current_effect.update()
                if state is not None:
                    self._apply_state(state)
            
        except Exception as e:
            logger.error(f"更新蜂鸣器效果失败: {e}")
    
    def set_effect(self, effect: EffectBase):
        """
        设置音效
        
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
        self.write(False)
    
    def _apply_state(self, state: bool):
        """
        内部方法：应用状态到硬件
        
        Args:
            state: True=开启，False=关闭
        """
        if self.simulate:
            return
        
        if self._gpio:
            if self.pwm_enabled and self._pwm:
                self._pwm.ChangeDutyCycle(50 if state else 0)
            else:
                self._gpio.output(self.pin, self._gpio.HIGH if state else self._gpio.LOW)
    
    def get_info(self) -> Dict[str, Any]:
        """
        获取设备信息
        
        Returns:
            设备信息字典
        """
        info = super().get_info()
        info.update({
            'pin': self.pin,
            'pwm_enabled': self.pwm_enabled,
            'default_frequency': self.default_frequency,
            'simulate': self.simulate,
            'is_active': self._is_active,
            'current_effect': self._current_effect.name if self._current_effect else None
        })
        return info
