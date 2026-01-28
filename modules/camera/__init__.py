"""
摄像头采集模块

提供视频采集功能，支持多种摄像头驱动：
- Picamera2（树莓派官方摄像头）
- OpenCV（通用 USB 摄像头）
- Simulator（测试模拟驱动）

主要组件：
- CameraProcess: 主进程类
- CameraDriverBase: 驱动抽象基类
- CaptureManager: 采集循环管理器
- CameraCommunicator: IPC 通信封装
- PerformanceMonitor: 性能监控统计

使用示例：
    from modules.camera import CameraProcess
    
    process = CameraProcess(ipc_client, shared_state, config)
    process.run()
"""

from .process import CameraProcess
from .base import CameraDriverBase
from .capture import CaptureManager
from .communicator import CameraCommunicator
from .monitor import PerformanceMonitor

# 驱动也可以直接导入
from .drivers import (
    Picamera2Driver,
    OpenCVDriver,
    SimulatorDriver
)

__all__ = [
    # 主要类
    'CameraProcess',
    
    # 核心组件
    'CameraDriverBase',
    'CaptureManager',
    'CameraCommunicator',
    'PerformanceMonitor',
    
    # 驱动实现
    'Picamera2Driver',
    'OpenCVDriver',
    'SimulatorDriver',
]

__version__ = '2.0.0'
