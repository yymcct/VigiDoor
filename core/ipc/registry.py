"""
进程注册表
统一管理所有进程的名称和元信息
"""

from dataclasses import dataclass
from typing import Dict, Optional
from enum import Enum


class ProcessName:
    """
    进程名称常量
    使用类常量避免拼写错误
    """
    
    # 核心进程
    SUPERVISOR = "supervisor"
    
    # 业务进程
    CAMERA = "camera"
    AI_DETECTOR = "ai_detector"
    AUDIO_PROCESSOR = "audio_processor"
    DEVICE_CONTROLLER = "device_controller"
    MQTT_CLIENT = "mqtt_client"
    STREAM_MANAGER = "stream_manager"
    
    @classmethod
    def all_processes(cls) -> list:
        """获取所有进程名称"""
        return [
            cls.SUPERVISOR,
            cls.CAMERA,
            cls.AI_DETECTOR,
            cls.AUDIO_PROCESSOR,
            cls.DEVICE_CONTROLLER,
            cls.MQTT_CLIENT,
            cls.STREAM_MANAGER,
        ]
    
    @classmethod
    def validate(cls, name: str) -> bool:
        """验证进程名称是否合法"""
        return name in cls.all_processes()


@dataclass
class ProcessInfo:
    """进程信息"""
    
    name: str
    description: str
    critical: bool = True       # 是否关键进程
    auto_restart: bool = True   # 是否自动重启
    
    def __hash__(self):
        return hash(self.name)


class ProcessRegistry:
    """
    进程注册表
    管理所有进程的元信息
    """
    
    # 静态注册表
    _registry: Dict[str, ProcessInfo] = {
        ProcessName.SUPERVISOR: ProcessInfo(
            name=ProcessName.SUPERVISOR,
            description="主进程监督者",
            critical=True,
            auto_restart=False,
        ),
        ProcessName.CAMERA: ProcessInfo(
            name=ProcessName.CAMERA,
            description="摄像头采集进程",
            critical=True,
            auto_restart=True,
        ),
        ProcessName.AI_DETECTOR: ProcessInfo(
            name=ProcessName.AI_DETECTOR,
            description="AI检测进程",
            critical=True,
            auto_restart=True,
        ),
        ProcessName.AUDIO_PROCESSOR: ProcessInfo(
            name=ProcessName.AUDIO_PROCESSOR,
            description="音频处理进程",
            critical=False,
            auto_restart=True,
        ),
        ProcessName.DEVICE_CONTROLLER: ProcessInfo(
            name=ProcessName.DEVICE_CONTROLLER,
            description="硬件控制进程",
            critical=True,
            auto_restart=True,
        ),
        ProcessName.MQTT_CLIENT: ProcessInfo(
            name=ProcessName.MQTT_CLIENT,
            description="MQTT通信进程",
            critical=True,
            auto_restart=True,
        ),
        ProcessName.STREAM_MANAGER: ProcessInfo(
            name=ProcessName.STREAM_MANAGER,
            description="流媒体管理进程",
            critical=False,
            auto_restart=True,
        ),
    }
    
    @classmethod
    def get(cls, name: str) -> Optional[ProcessInfo]:
        """获取进程信息"""
        return cls._registry.get(name)
    
    @classmethod
    def register(cls, info: ProcessInfo) -> None:
        """注册新进程"""
        cls._registry[info.name] = info
    
    @classmethod
    def unregister(cls, name: str) -> None:
        """注销进程"""
        if name in cls._registry:
            del cls._registry[name]
    
    @classmethod
    def all(cls) -> Dict[str, ProcessInfo]:
        """获取所有注册的进程"""
        return cls._registry.copy()
    
    @classmethod
    def is_critical(cls, name: str) -> bool:
        """判断是否为关键进程"""
        info = cls.get(name)
        return info.critical if info else False
    
    @classmethod
    def should_auto_restart(cls, name: str) -> bool:
        """判断是否应自动重启"""
        info = cls.get(name)
        return info.auto_restart if info else True
