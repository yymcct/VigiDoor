"""
流媒体管理模块

提供视频流的 OSD 渲染和推流功能：
- OSD 渲染（时间戳、检测框、设备信息）
- H.264 视频编码
- RTSP/RTMP 推流

架构：
- StreamManagerProcess: 主进程类
- StreamPipeline: 处理管道（协调渲染和编码）
- OSDRenderer: OSD 渲染器
- FFmpegEncoder: FFmpeg 编码器
- StateManager: 状态管理器

使用示例：
    from modules.stream import StreamManagerProcess
    
    process = StreamManagerProcess(ipc_client, shared_state, config)
    process.run()
"""

from .process import StreamManagerProcess
from .state import StreamState, StateManager
from .pipeline import StreamPipeline
from .frame_queue import FrameQueue

# OSD 组件
from .osd import (
    OSDRenderer,
    OSDElement,
    TimestampElement,
    DeviceInfoElement,
    DetectionBoxElement,
    CompositeOSDElement
)

# 编码器
from .encoder import (
    EncoderBase,
    FFmpegEncoder
)

__all__ = [
    # 主要类
    'StreamManagerProcess',
    
    # 核心组件
    'StreamState',
    'StateManager',
    'StreamPipeline',
    'FrameQueue',
    
    # OSD 组件
    'OSDRenderer',
    'OSDElement',
    'TimestampElement',
    'DeviceInfoElement',
    'DetectionBoxElement',
    'CompositeOSDElement',
    
    # 编码器
    'EncoderBase',
    'FFmpegEncoder',
]

__version__ = '2.0.0'
