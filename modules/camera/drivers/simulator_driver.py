"""
模拟驱动实现
用于测试环境，生成彩色渐变测试帧
"""

from typing import Optional
import numpy as np
import cv2
from utils.logger import setup_logger
from ..base import CameraDriverBase

logger = setup_logger('simulator_driver')


class SimulatorDriver(CameraDriverBase):
    """
    模拟驱动（测试用）
    生成彩色渐变动画帧
    """
    
    def __init__(self, width: int, height: int, target_fps: int, format: str):
        super().__init__(width, height, target_fps, format)
        self.frame_count = 0
    
    def initialize(self) -> bool:
        """初始化模拟驱动"""
        logger.info("🎬 初始化模拟驱动（测试模式）")
        self._is_initialized = True
        logger.info("✅ 模拟驱动初始化成功")
        return True
    
    def capture_frame(self) -> Optional[np.ndarray]:
        """生成测试帧"""
        if not self._is_initialized:
            return None
        
        try:
            frame = self._generate_test_frame(self.frame_count)
            self.frame_count += 1
            return frame
        except Exception as e:
            logger.error(f"生成测试帧失败: {e}")
            return None
    
    def _generate_test_frame(self, frame_id: int) -> np.ndarray:
        """
        生成彩色渐变测试帧
        
        Args:
            frame_id: 帧序号
            
        Returns:
            np.ndarray: RGB 图像
        """
        # 创建渐变背景
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        # 时间动画效果（100 帧一个循环）
        phase = (frame_id % 100) / 100.0
        
        # RGB 渐变动画
        frame[:, :, 0] = int(127 + 127 * np.sin(phase * 2 * np.pi))  # R
        frame[:, :, 1] = int(127 + 127 * np.sin((phase + 0.33) * 2 * np.pi))  # G
        frame[:, :, 2] = int(127 + 127 * np.sin((phase + 0.67) * 2 * np.pi))  # B
        
        # 添加文字信息
        try:
            text = f"SIMULATOR - Frame: {frame_id}"
            cv2.putText(
                frame, text, (50, 50),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2
            )
            
            # 添加分辨率信息
            res_text = f"{self.width}x{self.height} @ {self.target_fps}fps"
            cv2.putText(
                frame, res_text, (50, 100),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 1
            )
        except Exception as e:
            logger.debug(f"添加文字失败: {e}")
        
        return frame
    
    def release(self):
        """释放资源"""
        logger.info("模拟驱动资源已释放")
        self._is_initialized = False
        self.frame_count = 0
    
    def get_info(self) -> dict:
        """获取驱动信息"""
        return {
            'driver_type': 'simulator',
            'description': '模拟测试驱动',
            'resolution': f"{self.width}x{self.height}",
            'target_fps': self.target_fps,
            'frames_generated': self.frame_count
        }
