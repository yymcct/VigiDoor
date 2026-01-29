"""
按钮输入设备实现
支持物理按钮和模拟模式
"""

import time
from typing import Callable, Optional, Dict, Any
from ..base import InputDevice
from utils.logger import setup_logger

logger = setup_logger('button')


class ButtonDevice(InputDevice):
    """
    按钮输入设备
    
    支持：
    - 单击检测
    - 长按检测
    - 双击检测（可选）
    - 按键消抖
    """
    
    def __init__(self, pin: int, pull_up: bool = True, 
                 debounce_time: float = 0.05, 
                 long_press_time: float = 2.0,
                 simulate: bool = False):
        """
        初始化按钮设备
        
        Args:
            pin: GPIO 引脚号
            pull_up: 是否使用上拉电阻（True=按下为LOW，False=按下为HIGH）
            debounce_time: 消抖时间（秒）
            long_press_time: 长按阈值时间（秒）
            simulate: 是否使用模拟模式
        """
        super().__init__(
            device_id=f"button_{pin}",
            device_type="button",
            name=f"Button (GPIO{pin})"
        )
        
        self.pin = pin
        self.pull_up = pull_up
        self.debounce_time = debounce_time
        self.long_press_time = long_press_time
        self.simulate = simulate
        
        self._gpio = None
        self._last_state = False
        self._press_start_time = None
        self._last_press_time = 0
        self._double_click_window = 0.5  # 双击检测窗口（秒）
    
    def initialize(self) -> bool:
        """
        初始化按钮
        
        Returns:
            是否初始化成功
        """
        try:
            if self.simulate:
                # 模拟模式
                logger.info(f"✅ 按钮初始化成功（模拟模式）")
                logger.info(f"  引脚: GPIO {self.pin}")
                logger.info(f"  模式: {'上拉' if self.pull_up else '下拉'}")
                self._initialized = True
                return True
            
            # 尝试初始化真实硬件
            try:
                import RPi.GPIO as GPIO
                
                GPIO.setmode(GPIO.BCM)
                
                if self.pull_up:
                    GPIO.setup(self.pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
                else:
                    GPIO.setup(self.pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
                
                self._gpio = GPIO
                
                logger.info("✅ 按钮初始化成功")
                logger.info(f"  引脚: GPIO {self.pin}")
                logger.info(f"  模式: {'上拉' if self.pull_up else '下拉'}")
                
                self._initialized = True
                return True
                
            except ImportError:
                logger.warning("RPi.GPIO 库未安装，切换到模拟模式")
                self.simulate = True
                self._initialized = True
                return True
                
        except Exception as e:
            logger.error(f"按钮初始化失败: {e}")
            self._initialized = False
            return False
    
    def cleanup(self):
        """清理资源"""
        try:
            if self._gpio:
                self._gpio.cleanup(self.pin)
            logger.info("按钮已清理")
        except Exception as e:
            logger.error(f"按钮清理失败: {e}")
    
    def read(self) -> bool:
        """
        读取按钮状态
        
        Returns:
            True=按下，False=未按下
        """
        if not self._initialized:
            return False
        
        try:
            if self.simulate:
                # 模拟模式：返回固定值
                return False
            
            # 真实硬件
            if self._gpio:
                state = self._gpio.input(self.pin)
                # 如果是上拉模式，按下时为LOW，需要反转
                return not state if self.pull_up else state
            
            return False
            
        except Exception as e:
            logger.error(f"读取按钮状态失败: {e}")
            return False
    
    def wait_for_press(self, timeout: Optional[float] = None) -> bool:
        """
        等待按钮按下（阻塞）
        
        Args:
            timeout: 超时时间（秒），None 表示无限等待
            
        Returns:
            是否检测到按下
        """
        start_time = time.time()
        
        while True:
            if self.read():
                # 等待释放（消抖）
                time.sleep(self.debounce_time)
                if self.read():
                    return True
            
            # 检查超时
            if timeout and (time.time() - start_time) > timeout:
                return False
            
            time.sleep(0.01)
    
    def detect_press_type(self) -> Optional[str]:
        """
        检测按键类型（单击/长按/双击）
        
        应在主循环中定期调用
        
        Returns:
            'click' - 单击
            'long_press' - 长按
            'double_click' - 双击
            None - 未检测到
        """
        current_state = self.read()
        current_time = time.time()
        
        # 按下事件
        if current_state and not self._last_state:
            self._press_start_time = current_time
            
            # 检查是否是双击
            if current_time - self._last_press_time < self._double_click_window:
                self._last_state = current_state
                return 'double_click'
        
        # 释放事件
        elif not current_state and self._last_state:
            if self._press_start_time:
                press_duration = current_time - self._press_start_time
                self._press_start_time = None
                self._last_press_time = current_time
                
                # 判断是长按还是单击
                if press_duration >= self.long_press_time:
                    self._last_state = current_state
                    return 'long_press'
                else:
                    self._last_state = current_state
                    return 'click'
        
        self._last_state = current_state
        return None
    
    def simulate_press(self):
        """
        模拟按下（仅用于测试）
        
        触发所有注册的回调
        """
        if self.simulate:
            logger.info("  [模拟] 按钮按下")
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
            'pull_up': self.pull_up,
            'simulate': self.simulate,
            'debounce_time': self.debounce_time,
            'long_press_time': self.long_press_time
        })
        return info
