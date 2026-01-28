"""
OpenCV 驱动实现
适用于通用 USB 摄像头
"""

import time
from typing import Optional
import numpy as np
import cv2
from utils.logger import setup_logger
from ..base import CameraDriverBase

logger = setup_logger('opencv_driver')


class OpenCVDriver(CameraDriverBase):
    """
    OpenCV 驱动（通用摄像头）
    """
    
    def __init__(self, width: int, height: int, target_fps: int, format: str, device_id: int = 0):
        super().__init__(width, height, target_fps, format)
        self.device_id = device_id
        self.camera = None
    
    def initialize(self) -> bool:
        """初始化 OpenCV VideoCapture"""
        try:
            logger.info(f"正在初始化 OpenCV 摄像头 (设备 ID: {self.device_id})...")
            
            self.camera = cv2.VideoCapture(self.device_id)
            
            if not self.camera.isOpened():
                logger.error("无法打开摄像头设备")
                return False
            
            # 设置摄像头参数
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            self.camera.set(cv2.CAP_PROP_FPS, self.target_fps)
            
            # 预热（丢弃前几帧）
            logger.info("摄像头预热中...")
            for _ in range(10):
                self.camera.read()
                time.sleep(0.1)
            
            self._is_initialized = True
            logger.info("✅ OpenCV 摄像头初始化成功")
            
            # 打印实际参数
            actual_width = int(self.camera.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = int(self.camera.get(cv2.CAP_PROP_FPS))
            logger.info(f"   实际分辨率: {actual_width}x{actual_height}")
            logger.info(f"   实际帧率: {actual_fps} FPS")
            
            return True
            
        except Exception as e:
            logger.error(f"OpenCV 摄像头初始化失败: {e}")
            return False
    
    def capture_frame(self) -> Optional[np.ndarray]:
        """捕获一帧（自动转换为 RGB）"""
        if not self._is_initialized or not self.camera:
            return None
        
        try:
            ret, frame = self.camera.read()
            if not ret:
                logger.error("读取帧失败")
                return None
            
            # OpenCV 返回 BGR，转换为 RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            return frame_rgb
            
        except Exception as e:
            logger.error(f"捕获帧失败: {e}")
            return None
    
    def release(self):
        """释放资源"""
        if self.camera:
            try:
                self.camera.release()
                logger.info("OpenCV 摄像头资源已释放")
            except Exception as e:
                logger.error(f"释放 OpenCV 资源失败: {e}")
            finally:
                self.camera = None
                self._is_initialized = False
    
    def get_info(self) -> dict:
        """获取驱动信息"""
        return {
            'driver_type': 'opencv',
            'description': '通用 USB 摄像头驱动',
            'device_id': self.device_id,
            'resolution': f"{self.width}x{self.height}",
            'target_fps': self.target_fps
        }
