"""
配置管理器
提供全局配置访问接口（单例模式）
"""

from typing import Optional, Dict, Any
import yaml
import threading
from pathlib import Path

from .sections import (
    RegionConfig,
    RegionDetectorConfig,
    DetectorConfig,
    OSDConfig,
    CameraConfig,
    StreamConfig,
    MQTTConfig,
    DeviceConfig,
    AudioConfig,
    HardwareConfig,
    LoggingConfig,
    SupervisorConfig,
    MonitoringConfig,
    StorageConfig
)
from ..device_id import generate_device_id


class ConfigManager:
    """
    配置管理器（单例）
    
    用法：
        # 初始化（在主进程启动时）
        ConfigManager.initialize('config.yaml')
        
        # 获取实例
        config = ConfigManager.get_instance()
        
        # 访问配置
        regions = config.detector.region_detector.regions
        osd_color = config.osd.region_overlay_color
        
        # 向后兼容：获取原始字典
        raw_config = config.get_raw_dict()
    """
    
    _instance: Optional['ConfigManager'] = None
    _lock = threading.Lock()
    
    def __init__(self, config_path: str = None):
        """
        私有构造函数，请使用 get_instance()
        """
        if ConfigManager._instance is not None:
            raise RuntimeError("请使用 ConfigManager.get_instance() 获取单例")
        
        self._config_path = config_path
        self._raw_config: Dict[str, Any] = {}
        
        # 类型化配置对象
        self.device: Optional[DeviceConfig] = None
        self.mqtt: Optional[MQTTConfig] = None
        self.camera: Optional[CameraConfig] = None
        self.stream: Optional[StreamConfig] = None
        self.audio: Optional[AudioConfig] = None
        self.detector: Optional[DetectorConfig] = None
        self.osd: Optional[OSDConfig] = None
        self.hardware: Optional[HardwareConfig] = None
        self.logging: Optional[LoggingConfig] = None
        self.supervisor: Optional[SupervisorConfig] = None
        self.monitoring: Optional[MonitoringConfig] = None
        self.storage: Optional[StorageConfig] = None
        
        if config_path:
            self.load(config_path)
    
    @classmethod
    def initialize(cls, config_path: str) -> 'ConfigManager':
        """
        初始化配置管理器（只需调用一次）
        
        Args:
            config_path: 配置文件路径
        
        Returns:
            ConfigManager实例
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(config_path)
        return cls._instance
    
    @classmethod
    def get_instance(cls) -> 'ConfigManager':
        """
        获取配置管理器单例
        
        Returns:
            ConfigManager实例
        
        Raises:
            RuntimeError: 如果未初始化
        """
        if cls._instance is None:
            raise RuntimeError(
                "ConfigManager 未初始化，请先调用 ConfigManager.initialize('config.yaml')"
            )
        return cls._instance
    
    @classmethod
    def reset(cls):
        """重置单例（主要用于测试）"""
        cls._instance = None
    
    def load(self, config_path: str):
        """
        加载配置文件
        
        Args:
            config_path: 配置文件路径
        """
        config_file = Path(config_path)
        
        if not config_file.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
        
        with open(config_file, 'r', encoding='utf-8') as f:
            self._raw_config = yaml.safe_load(f)
        
        self._config_path = config_path
        self._parse_config()
    
    def reload(self):
        """重新加载配置文件"""
        if self._config_path:
            self.load(self._config_path)
    
    def _parse_config(self):
        """解析配置到类型化对象"""
        raw = self._raw_config
        
        # 解析设备配置
        device_raw = raw.get('device', {})
        
        # 自动生成设备ID（不再从配置文件读取）
        auto_device_id = generate_device_id()
        
        self.device = DeviceConfig(
            id=auto_device_id,  # 使用自动生成的设备ID
            name=device_raw.get('name', ''),
            location=device_raw.get('location', '')
        )
        
        # 解析MQTT配置
        mqtt_raw = raw.get('mqtt', {})
        
        # client_id 使用自动生成的设备ID（如果配置文件未指定）
        client_id = mqtt_raw.get('client_id', '')
        if not client_id or client_id == '{device_id}':
            client_id = auto_device_id
        
        self.mqtt = MQTTConfig(
            broker_host=mqtt_raw.get('broker_host', ''),
            broker_port=mqtt_raw.get('broker_port', 8883),
            username=mqtt_raw.get('username', ''),
            password=mqtt_raw.get('password', ''),
            client_id=client_id,
            keepalive=mqtt_raw.get('keepalive', 60),
            qos=mqtt_raw.get('qos', 1),
            tls_ca=mqtt_raw.get('tls_ca', ''),
            tls_insecure=mqtt_raw.get('tls_insecure', False)
        )
        
        # 解析摄像头配置
        camera_raw = raw.get('camera', {})
        self.camera = CameraConfig(
            width=camera_raw.get('width', 1280),
            height=camera_raw.get('height', 720),
            target_fps=camera_raw.get('target_fps', 15),
            format=camera_raw.get('format', 'RGB888'),
            shared_memory_name=camera_raw.get('shared_memory_name', 'vigidoor_frames')
        )
        
        # 解析流媒体配置
        stream_raw = raw.get('stream', {})
        self.stream = StreamConfig(
            zlm_server=stream_raw.get('zlm_server', ''),
            stream_key=stream_raw.get('stream_key', ''),
            video_codec=stream_raw.get('video_codec', 'h264'),
            audio_codec=stream_raw.get('audio_codec', 'aac'),
            bitrate=stream_raw.get('bitrate', '1000k'),
            fps=stream_raw.get('fps', 25),
            resolution=stream_raw.get('resolution', '1280x720')
        )
        
        # 解析音频配置
        audio_raw = raw.get('audio', {})
        self.audio = AudioConfig(
            sample_rate=audio_raw.get('sample_rate', 16000),
            channels=audio_raw.get('channels', 1),
            chunk_size=audio_raw.get('chunk_size', 1024),
            anomaly_threshold=audio_raw.get('anomaly_threshold', 0.8)
        )
        
        # 解析区域配置
        regions = []
        pipeline_config = raw.get('ai_detector', {}).get('pipeline', [])
        for stage in pipeline_config:
            if stage.get('type') == 'region':
                region_data = stage.get('config', {}).get('regions', [])
                for r in region_data:
                    regions.append(RegionConfig(
                        name=r.get('name', 'Unknown'),
                        type=r.get('type', 'rect'),
                        enabled=r.get('enabled', True),
                        coords=r.get('coords', [])
                    ))
        
        # 解析检测器配置
        detector_raw = raw.get('ai_detector', {})
        
        # 查找区域检测器配置
        region_detector_config = None
        overlap_threshold = 0.1
        for stage in pipeline_config:
            if stage.get('type') == 'region':
                overlap_threshold = stage.get('config', {}).get('overlap_threshold', 0.1)
                break
        
        if regions:
            region_detector_config = RegionDetectorConfig(
                overlap_threshold=overlap_threshold,
                regions=regions
            )
        
        self.detector = DetectorConfig(
            model_path=detector_raw.get('model_path', ''),
            confidence_threshold=detector_raw.get('confidence_threshold', 0.5),
            target_classes=detector_raw.get('target_classes', [0]),
            detect_interval=detector_raw.get('detect_interval', 8),
            safe_interval=detector_raw.get('safe_interval', 8),
            alert_interval=detector_raw.get('alert_interval', 3),
            alarm_interval=detector_raw.get('alarm_interval', 1),
            alarm_cooldown=detector_raw.get('alarm_cooldown', 5.0),
            region_detector=region_detector_config
        )
        
        # 解析OSD配置（支持从配置文件读取或使用默认值）
        osd_raw = raw.get('osd', {})
        self.osd = OSDConfig(
            timestamp_enabled=osd_raw.get('timestamp_enabled', True),
            device_info_enabled=osd_raw.get('device_info_enabled', True),
            detection_box_enabled=osd_raw.get('detection_box_enabled', True),
            region_overlay_enabled=osd_raw.get('region_overlay_enabled', True),
            region_overlay_color=tuple(osd_raw.get('region_overlay_color', [255, 255, 0])),
            region_overlay_thickness=osd_raw.get('region_overlay_thickness', 2),
            region_overlay_alpha=osd_raw.get('region_overlay_alpha', 0.3),
            region_label_font_scale=osd_raw.get('region_label_font_scale', 0.5),
            box_thickness=osd_raw.get('box_thickness', 2),
            text_font_scale=osd_raw.get('text_font_scale', 0.5),
            text_thickness=osd_raw.get('text_thickness', 2)
        )
        
        # 解析硬件配置
        hardware_raw = raw.get('hardware', {})
        self.hardware = HardwareConfig(
            led_strip=hardware_raw.get('led_strip', {})
        )
        
        # 解析日志配置
        logging_raw = raw.get('logging', {})
        self.logging = LoggingConfig(
            level=logging_raw.get('level', 'INFO'),
            max_file_size=logging_raw.get('max_file_size', 10485760),
            backup_count=logging_raw.get('backup_count', 5),
            format=logging_raw.get('format', '%(asctime)s [%(levelname)s] %(message)s')
        )
        
        # 解析进程管理配置
        supervisor_raw = raw.get('supervisor', {})
        self.supervisor = SupervisorConfig(
            restart_limit=supervisor_raw.get('restart_limit', 5),
            restart_window=supervisor_raw.get('restart_window', 300),
            alarm_auto_reset_seconds=supervisor_raw.get('alarm_auto_reset_seconds', 0),
            heartbeat_interval=supervisor_raw.get('heartbeat_interval', 5),
            heartbeat_timeout=supervisor_raw.get('heartbeat_timeout', 30),
            startup_delays=supervisor_raw.get('startup_delays', {})
        )
        
        # 解析监控配置
        monitoring_raw = raw.get('monitoring', {})
        self.monitoring = MonitoringConfig(
            health_report_interval=monitoring_raw.get('health_report_interval', 60),
            watchdog_feed_interval=monitoring_raw.get('watchdog_feed_interval', 30),
            thresholds=monitoring_raw.get('thresholds', {})
        )
        
        # 解析存储配置
        storage_raw = raw.get('storage', {})
        self.storage = StorageConfig(
            snapshot_dir=storage_raw.get('snapshot_dir', './data/snapshots'),
            cache_dir=storage_raw.get('cache_dir', './data/cache'),
            max_snapshot_age=storage_raw.get('max_snapshot_age', 86400),
            max_cache_size=storage_raw.get('max_cache_size', 1073741824)
        )
    
    def get_raw_dict(self) -> Dict[str, Any]:
        """
        获取原始配置字典（向后兼容）
        
        Returns:
            原始配置字典
        """
        return self._raw_config.copy()
    
    def get_raw(self, key_path: str, default=None):
        """
        获取原始配置值（向后兼容）
        
        Args:
            key_path: 配置路径，用点号分隔（如 'ai_detector.model_path'）
            default: 默认值
        
        Returns:
            配置值或默认值
        
        示例：
            config.get_raw('ai_detector.model_path')
            config.get_raw('camera.width', 1280)
        """
        keys = key_path.split('.')
        value = self._raw_config
        
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
                if value is None:
                    return default
            else:
                return default
        
        return value
