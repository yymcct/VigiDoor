"""
OSD 模块
"""

from .elements import (
    OSDElement,
    TimestampElement,
    DeviceInfoElement,
    DetectionBoxElement,
    SkeletonElement,
    RegionOverlayElement,
    FootTrafficElement,
    CompositeOSDElement
)
from .renderer import OSDRenderer
from .data_store import OSDDataStore
from .dispatcher import OSDMessageDispatcher

__all__ = [
    'OSDElement',
    'TimestampElement',
    'DeviceInfoElement',
    'DetectionBoxElement',
    'SkeletonElement',
    'RegionOverlayElement',
    'FootTrafficElement',
    'CompositeOSDElement',
    'OSDRenderer',
    'OSDDataStore',
    'OSDMessageDispatcher',
]
