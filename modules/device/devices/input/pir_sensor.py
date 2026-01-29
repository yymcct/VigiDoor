"""
PIR 运动传感器实现
用于检测人体移动
"""

import time
from typing import Optional, Dict, Any
from ..base import InputDevice
from utils.logger import setup_logger

logger = setup_logger('pir_sensor')


class PIRSensor(InputDevice):
    """
    PIR 运动传感器
    
    特性：
    - 检测人体红外辐射
    - 触发/静止状态
    - 可配置触发延迟
    """
    
    def __init__(self, pin: int, trigger_delay: float = 0.5, simulate: bool = False):
        """
        初始化 PIR 传感器
        
        Args:
            pin: GPIO 引脚号
            trigger_delay: 触发延迟（秒），防止误触发
            simulate: 是否使用模拟模式
        """
        super().__init__(
            device_id=f"pir_{pin}",
            device_type="pir_sensor",
            name=f"PIR Sensor (GPIO{pin})"
        )
        
        self.pin = pin
        self.trigger_delay = trigger_delay
        self.simulate = simulate
        
        self._gpio = None
        self._last_trigger_time = 0
        self._is_triggered = False
    
    def initialize(self) -> bool:
        """
        初始化 PIR 传感器
        
        Returns:
            是否初始化成功
        """
        try:
            if self.simulate:
                # 模拟模式
                logger.info(f"✅ PIR 传感器初始化成功（模拟模式）")
                logger.info(f"  引脚: GPIO {self.pin}")
                logger.info(f"  触发延迟: {self.trigger_delay}秒")
                self._initialized = True
                return True
            
            # 尝试初始化真实硬件
            try:
                import RPi.GPIO as GPIO
                
                GPIO.setmode(GPIO.BCM)
                GPIO.setup(self.pin, GPIO.IN)
                
                self._gpio = GPIO
                
                logger.info("✅ PIR 传感器初始化成功")
                logger.info(f"  引脚: GPIO {self.pin}")
                logger.info(f"  触发延迟: {self.trigger_delay}秒")
                
                # 等待传感器稳定（通常需要 1-2 秒）
                logger.info("  等待传感器稳定...")
                time.sleep(2)
                logger.info("  传感器已就绪")
                
                self._initialized = True
                return True
                
            except ImportError:
                logger.warning("RPi.GPIO 库未安装，切换到模拟模式")
                self.simulate = True
                self._initialized = True
                return True
                
        except Exception as e:
            logger.error(f"PIR 传感器初始化失败: {e}")
            self._initialized = False
            return False
    
    def cleanup(self):
        """清理资源"""
        try:
            if self._gpio:
                self._gpio.cleanup(self.pin)
            logger.info("PIR 传感器已清理")
        except Exception as e:
            logger.error(f"PIR 传感器清理失败: {e}")
    
    def read(self) -> bool:
        """
        读取 PIR 传感器状态
        
        Returns:
            True=检测到运动，False=未检测到
        """
        if not self._initialized:
            return False
        
        try:
            if self.simulate:
                # 模拟模式：返回固定值
                return False
            
            # 真实硬件
            if self._gpio:
                state = self._gpio.input(self.pin) == 1
                
                # 应用触发延迟
                current_time = time.time()
                if state:
                    if current_time - self._last_trigger_time > self.trigger_delay:
                        self._last_trigger_time = current_time
                        self._is_triggered = True
                        return True
                else:
                    self._is_triggered = False
                
                return self._is_triggered
            
            return False
            
        except Exception as e:
            logger.error(f"读取 PIR 状态失败: {e}")
            return False
    
    def wait_for_motion(self, timeout: Optional[float] = None) -> bool:
        """
        等待检测到运动（阻塞）
        
        Args:
            timeout: 超时时间（秒），None 表示无限等待
            
        Returns:
            是否检测到运动
        """
        start_time = time.time()
        
        while True:
            if self.read():
                return True
            
            # 检查超时
            if timeout and (time.time() - start_time) > timeout:
                return False
            
            time.sleep(0.1)
    
    def is_motion_detected(self) -> bool:
        """
        检查是否检测到运动
        
        Returns:
            是否检测到运动
        """
        return self.read()
    
    def simulate_motion(self):
        """
        模拟检测到运动（仅用于测试）
        
        触发所有注册的回调
        """
        if self.simulate:
            logger.info("  [模拟] 检测到运动")
            self._trigger_callbacks(True)
    
    def get_info(self) -> Dict[str, Any]:
        """
        获取设备信息
        
        Returns:
            设备信息字典
        """
        info = super().get_info()
        info.update({
            'pin': self.pin,
            'simulate': self.simulate,
            'trigger_delay': self.trigger_delay,
            'is_triggered': self._is_triggered
        })
        return info
