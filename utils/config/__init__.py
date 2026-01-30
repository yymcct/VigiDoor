"""
配置管理模块
提供类型安全的配置访问接口
"""

from .manager import ConfigManager
from .sections import (
    RegionConfig,
    RegionDetectorConfig,
    DetectorConfig,
    OSDConfig,
    CameraConfig,
    StreamConfig,
    MQTTConfig,
    DeviceConfig
)

__all__ = [
    'ConfigManager',
    'RegionConfig',
    'RegionDetectorConfig',
    'DetectorConfig',
    'OSDConfig',
    'CameraConfig',
    'StreamConfig',
    'MQTTConfig',
    'DeviceConfig'
]
