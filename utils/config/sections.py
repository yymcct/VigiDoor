"""
配置数据类
提供类型安全的配置对象
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Any, Optional


@dataclass
class RegionConfig:
    """区域配置"""
    name: str
    type: str  # 'rect' or 'polygon'
    enabled: bool
    coords: List[float]
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'name': self.name,
            'type': self.type,
            'enabled': self.enabled,
            'coords': self.coords
        }


@dataclass
class RegionDetectorConfig:
    """区域检测器配置"""
    overlap_threshold: float
    regions: List[RegionConfig] = field(default_factory=list)


@dataclass
class DetectorConfig:
    """AI检测器配置"""
    model_path: str
    confidence_threshold: float
    target_classes: List[int]
    detect_interval: int
    safe_interval: int
    alert_interval: int
    alarm_interval: int
    alarm_cooldown: float
    region_detector: Optional[RegionDetectorConfig] = None


@dataclass
class OSDConfig:
    """OSD配置"""
    timestamp_enabled: bool = True
    device_info_enabled: bool = True
    detection_box_enabled: bool = True
    
    # 区域叠加配置
    region_overlay_enabled: bool = True
    region_overlay_color: Tuple[int, int, int] = (255, 255, 0)  # 黄色
    region_overlay_thickness: int = 2
    region_overlay_alpha: float = 0.3
    region_label_font_scale: float = 0.5
    
    # 检测框配置
    box_thickness: int = 2
    text_font_scale: float = 0.5
    text_thickness: int = 2


@dataclass
class CameraConfig:
    """摄像头配置"""
    width: int
    height: int
    target_fps: int
    format: str
    shared_memory_name: str


@dataclass
class StreamConfig:
    """流媒体配置"""
    zlm_server: str
    stream_key: str
    video_codec: str
    audio_codec: str
    bitrate: str
    fps: int
    resolution: str


@dataclass
class MQTTConfig:
    """MQTT配置"""
    broker_host: str
    broker_port: int
    username: str
    password: str
    client_id: str
    keepalive: int
    qos: int
    tls_ca: str
    tls_insecure: bool


@dataclass
class DeviceConfig:
    """设备配置"""
    id: str
    name: str
    location: str


@dataclass
class AudioConfig:
    """音频配置"""
    sample_rate: int
    channels: int
    chunk_size: int
    anomaly_threshold: float


@dataclass
class HardwareConfig:
    """硬件配置"""
    led_strip: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LoggingConfig:
    """日志配置"""
    level: str
    max_file_size: int
    backup_count: int
    format: str


@dataclass
class SupervisorConfig:
    """进程管理配置"""
    restart_limit: int
    restart_window: int
    alarm_auto_reset_seconds: float
    heartbeat_interval: int
    heartbeat_timeout: int
    startup_delays: Dict[str, float] = field(default_factory=dict)


@dataclass
class MonitoringConfig:
    """监控配置"""
    health_report_interval: int
    watchdog_feed_interval: int
    thresholds: Dict[str, int] = field(default_factory=dict)


@dataclass
class StorageConfig:
    """存储配置"""
    snapshot_dir: str
    cache_dir: str
    max_snapshot_age: int
    max_cache_size: int
