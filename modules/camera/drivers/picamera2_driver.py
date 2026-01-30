"""
Picamera2 驱动实现
适用于树莓派官方摄像头模块
"""

import time
from typing import Optional
import numpy as np
from utils.logger import setup_logger
from ..base import CameraDriverBase

logger = setup_logger('picamera2_driver')


class Picamera2Driver(CameraDriverBase):
    """
    Picamera2 驱动（树莓派官方摄像头）
    """
    
    def __init__(self, width: int, height: int, target_fps: int, format: str):
        super().__init__(width, height, target_fps, format)
        self.camera = None
    
    def initialize(self) -> bool:
        """初始化 Picamera2"""
        try:
            from picamera2 import Picamera2
            
            logger.info("正在初始化 Picamera2...")
            self.camera = Picamera2()
            
            # 配置摄像头
            config = self.camera.create_preview_configuration(
                main={
                    "size": (self.width, self.height),
                    "format": self.format
                }
            )
            self.camera.configure(config)
            
            # 启动摄像头
            self.camera.start()
            
            # 预热（丢弃前几帧）
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
            frame = self.camera.capture_array()
            return frame
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
            'resolution': f"{self.width}x{self.height}",
            'target_fps': self.target_fps,
            'format': self.format
        }
