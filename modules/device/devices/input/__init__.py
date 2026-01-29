"""
输入设备实现
"""

from .button import ButtonDevice
from .pir_sensor import PIRSensor

# 预留其他输入设备：
# - microphone.py: 麦克风输入
# - light_sensor.py: 光照传感器
# - temperature_sensor.py: 温度传感器
# 等等

__all__ = [
    'ButtonDevice',
    'PIRSensor'
]
