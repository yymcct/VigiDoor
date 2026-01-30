"""
输出设备实现
"""

from .led_strip import LEDStripDevice
from .relay import RelayDevice

# 预留其他输出设备：
# - servo.py: 舵机
# - motor.py: 电机
# - display.py: OLED/LCD 显示屏
# 等等

__all__ = [
    'LEDStripDevice',
    'RelayDevice'
]
