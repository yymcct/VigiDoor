"""
Picamera2 驱动实现
适用于树莓派官方摄像头模块，支持 OV5647 / IMX708 传感器自动适配
"""

import time
from typing import Optional
import numpy as np
from utils.logger import setup_logger
from ..base import CameraDriverBase
from .sensor_detect import detect_sensor_model, SENSOR_OV5647, SENSOR_IMX708

logger = setup_logger('picamera2_driver')


def _build_ov5647_controls() -> dict:
    """OV5647（Camera Module V1，500 万像素）画质控制参数"""
    return {
        "Sharpness": 1.5,         # 锐度 (0.0-16.0，默认 1.0)
        "Contrast": 1.2,          # 对比度
        "Saturation": 1.1,        # 饱和度
        "NoiseReductionMode": 2,  # 降噪: 2=HighQuality
        "AwbMode": 0,             # AWB: 0=Auto
    }


def _build_imx708_controls() -> dict:
    """
    IMX708（Camera Module V3，1200 万像素）画质控制参数。
    IMX708 支持更宽动态范围，针对其特性进行优化。
    """
    return {
        "Sharpness": 1.5,           # 适度锐化，避免过曝噪点
        "Contrast": 1.15,           # 轻微提升对比度
        "Saturation": 1.1,          # 轻微提升饱和度
        "NoiseReductionMode": 2,    # 降噪: 2=HighQuality
        "AwbMode": 0,               # AWB: 0=Auto
        "AeExposureMode": 0,        # 曝光模式: 0=Normal（保留高动态范围）
        "AeMeteringMode": 0,        # 测光: 0=CentreWeighted
        "ExposureValue": 0.0,       # EV 补偿 (-8.0~8.0)
        # "ColourGains": (1.8, 1.6),  # 已禁用：手动 R/B 增益会干扰 AWB，导致偏红；由 AWB Auto 自动管理
    }


class Picamera2Driver(CameraDriverBase):
    """
    Picamera2 驱动（树莓派官方摄像头）
    支持 OV5647 / IMX708 传感器自动检测与差异化画质配置。
    """

    def __init__(self, width: int, height: int, target_fps: int, format: str):
        super().__init__(width, height, target_fps, format)
        self.camera = None
        self._sensor_model: str = ""

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    def _build_camera_config(self):
        """根据已检测到的传感器型号构建 video 配置"""
        if SENSOR_IMX708 in self._sensor_model:
            controls = _build_imx708_controls()
            logger.info("使用 IMX708 专属画质配置")
        else:
            controls = _build_ov5647_controls()
            if SENSOR_OV5647 in self._sensor_model:
                logger.info("使用 OV5647 画质配置")
            else:
                logger.warning(f"未知传感器型号 '{self._sensor_model}'，回退到默认 OV5647 配置")

        return self.camera.create_video_configuration(
            main={
                "size": (self.width, self.height),
                "format": self.format,
            },
            controls=controls,
        )

    # ------------------------------------------------------------------
    # CameraDriverBase 接口实现
    # ------------------------------------------------------------------

    def initialize(self) -> bool:
        """初始化 Picamera2，自动检测传感器并应用对应画质配置"""
        try:
            from picamera2 import Picamera2

            logger.info("正在初始化 Picamera2...")
            self.camera = Picamera2()

            # 探测传感器型号
            self._sensor_model = detect_sensor_model(self.camera)
            logger.info(f"检测到摄像头传感器: '{self._sensor_model or '未知'}'")

            # 构建并应用配置
            config = self._build_camera_config()
            self.camera.configure(config)

            # 启动摄像头
            self.camera.start()

            # 预热（丢弃前几帧，待 AE/AWB 稳定）
            logger.info("摄像头预热中...")
            for _ in range(10):
                self.camera.capture_array()
                time.sleep(0.1)

            self._is_initialized = True
            logger.info("✅ Picamera2 初始化成功")
            return True

        except ImportError:
            logger.warning("Picamera2 库不可用")
            return False
        except Exception as e:
            logger.error(f"Picamera2 初始化失败: {e}")
            return False

    def capture_frame(self) -> Optional[np.ndarray]:
        """捕获一帧"""
        if not self._is_initialized or not self.camera:
            return None

        try:
            return self.camera.capture_array()
        except Exception as e:
            logger.error(f"捕获帧失败: {e}")
            return None

    def release(self):
        """释放资源"""
        if self.camera:
            try:
                # 仅停止采集，避免显式 close 导致 __del__ 再次 close 报错
                # Picamera2.__del__ 会在对象销毁时自动 close
                self.camera.stop()
                logger.info("Picamera2 采集已停止")
            except Exception as e:
                logger.error(f"释放 Picamera2 资源失败: {e}")
            finally:
                self.camera = None
                self._is_initialized = False

    def get_info(self) -> dict:
        """获取驱动信息"""
        return {
            'driver_type': 'picamera2',
            'description': '树莓派官方摄像头驱动',
            'sensor_model': self._sensor_model or 'unknown',
            'resolution': f"{self.width}x{self.height}",
            'target_fps': self.target_fps,
            'format': self.format,
        }
