"""
OSD 模块
"""

from .elements import (
    OSDElement,
    TimestampElement,
    DeviceInfoElement,
    DetectionBoxElement,
    CompositeOSDElement
)
from .renderer import OSDRenderer

__all__ = [
    'OSDElement',
    'TimestampElement',
    'DeviceInfoElement',
    'DetectionBoxElement',
    'CompositeOSDElement',
    'OSDRenderer',
]
