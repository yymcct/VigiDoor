"""
LED 灯效实现
包含常用的 LED 动画效果
"""

import time
from typing import Tuple, Optional
from .base import EffectBase


class SolidColorEffect(EffectBase):
    """纯色效果"""
    
    def __init__(self, color: Tuple[int, int, int]):
        """
        Args:
            color: RGB 颜色值 (0-255, 0-255, 0-255)
        """
        super().__init__("SolidColor")
        self.color = color
        self._result = None
    
    def start(self):
        """启动效果"""
        self._is_running = True
        self._result = self.color
    
    def update(self):
        """更新效果（纯色不需要更新）"""
        return self._result
    
    def stop(self):
        """停止效果"""
        self._is_running = False
        self._result = None


class BlinkEffect(EffectBase):
    """闪烁效果"""
    
    def __init__(self, color: Tuple[int, int, int], interval: float = 0.5):
        """
        Args:
            color: RGB 颜色值
            interval: 闪烁间隔（秒）
        """
        super().__init__("Blink")
        self.color = color
        self.interval = interval
        self._last_toggle = 0
        self._is_on = False
    
    def start(self):
        """启动效果"""
        self._is_running = True
        self._last_toggle = time.time()
        self._is_on = True
    
    def update(self):
        """更新闪烁状态"""
        if not self._is_running:
            return None
        
        current_time = time.time()
        if current_time - self._last_toggle >= self.interval:
            self._is_on = not self._is_on
            self._last_toggle = current_time
        
        return self.color if self._is_on else (0, 0, 0)
    
    def stop(self):
        """停止效果"""
        self._is_running = False


class BreathEffect(EffectBase):
    """呼吸灯效果"""
    
    def __init__(self, color: Tuple[int, int, int], period: float = 2.0):
        """
        Args:
            color: RGB 颜色值
            period: 呼吸周期（秒）
        """
        super().__init__("Breath")
        self.color = color
        self.period = period
        self._start_time = 0
    
    def start(self):
        """启动效果"""
        self._is_running = True
        self._start_time = time.time()
    
    def update(self):
        """更新呼吸效果"""
        if not self._is_running:
            return None
        
        # 计算亮度（正弦波）
        elapsed = time.time() - self._start_time
        brightness = (1 + __import__('math').sin(2 * __import__('math').pi * elapsed / self.period)) / 2
        
        # 应用亮度到颜色
        return tuple(int(c * brightness) for c in self.color)
    
    def stop(self):
        """停止效果"""
        self._is_running = False


class RainbowEffect(EffectBase):
    """彩虹循环效果"""
    
    def __init__(self, period: float = 3.0):
        """
        Args:
            period: 彩虹循环周期（秒）
        """
        super().__init__("Rainbow")
        self.period = period
        self._start_time = 0
    
    def start(self):
        """启动效果"""
        self._is_running = True
        self._start_time = time.time()
    
    def update(self):
        """更新彩虹效果"""
        if not self._is_running:
            return None
        
        # 计算色相值（0-360度）
        elapsed = time.time() - self._start_time
        hue = (elapsed / self.period * 360) % 360
        
        # HSV 转 RGB
        return self._hsv_to_rgb(hue, 1.0, 1.0)
    
    def stop(self):
        """停止效果"""
        self._is_running = False
    
    @staticmethod
    def _hsv_to_rgb(h: float, s: float, v: float) -> Tuple[int, int, int]:
        """
        HSV 转 RGB
        
        Args:
            h: 色相 (0-360)
            s: 饱和度 (0-1)
            v: 明度 (0-1)
            
        Returns:
            RGB 元组 (0-255, 0-255, 0-255)
        """
        h = h / 60.0
        i = int(h)
        f = h - i
        
        p = v * (1 - s)
        q = v * (1 - s * f)
        t = v * (1 - s * (1 - f))
        
        if i == 0:
            r, g, b = v, t, p
        elif i == 1:
            r, g, b = q, v, p
        elif i == 2:
            r, g, b = p, v, t
        elif i == 3:
            r, g, b = p, q, v
        elif i == 4:
            r, g, b = t, p, v
        else:
            r, g, b = v, p, q
        
        return (int(r * 255), int(g * 255), int(b * 255))


class PulseEffect(EffectBase):
    """脉冲效果（快速闪烁多次）"""
    
    def __init__(self, color: Tuple[int, int, int], pulse_count: int = 3, pulse_interval: float = 0.1):
        """
        Args:
            color: RGB 颜色值
            pulse_count: 脉冲次数
            pulse_interval: 脉冲间隔（秒）
        """
        super().__init__("Pulse")
        self.color = color
        self.pulse_count = pulse_count
        self.pulse_interval = pulse_interval
        self._start_time = 0
        self._current_pulse = 0
    
    def start(self):
        """启动效果"""
        self._is_running = True
        self._start_time = time.time()
        self._current_pulse = 0
    
    def update(self):
        """更新脉冲效果"""
        if not self._is_running:
            return None
        
        elapsed = time.time() - self._start_time
        pulse_position = elapsed / self.pulse_interval
        
        # 检查是否完成所有脉冲
        if pulse_position >= self.pulse_count * 2:
            self._is_running = False
            return (0, 0, 0)
        
        # 计算当前脉冲状态（奇数=亮，偶数=暗）
        is_on = int(pulse_position) % 2 == 0
        return self.color if is_on else (0, 0, 0)
    
    def stop(self):
        """停止效果"""
        self._is_running = False
