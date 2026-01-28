"""
性能监控模块
负责 FPS 统计和性能指标监控
"""

import time
from utils.logger import setup_logger

logger = setup_logger('camera_monitor')


class PerformanceMonitor:
    """
    性能监控器
    
    功能：
    - FPS 统计
    - 帧计数
    - 性能异常检测和告警
    """
    
    def __init__(self, target_fps: int, low_fps_threshold: float = 0.8):
        """
        初始化性能监控器
        
        Args:
            target_fps: 目标帧率
            low_fps_threshold: 低帧率告警阈值（默认 80%）
        """
        self.target_fps = target_fps
        self.low_fps_threshold = low_fps_threshold
        
        # 统计信息
        self.frame_count = 0
        self.fps_counter = 0
        self.current_fps = 0
        self.last_fps_check = time.time()
        
        # 告警状态
        self._low_fps_warned = False
    
    def on_frame_captured(self):
        """
        帧捕获事件回调
        每捕获一帧时调用
        """
        self.frame_count += 1
        self.fps_counter += 1
    
    def update(self) -> bool:
        """
        更新性能统计（每秒调用一次）
        
        Returns:
            bool: 如果需要更新 FPS 统计返回 True
        """
        now = time.time()
        
        if now - self.last_fps_check >= 1.0:
            # 计算当前 FPS
            self.current_fps = self.fps_counter
            self.fps_counter = 0
            self.last_fps_check = now
            
            # 检测帧率异常
            self._check_fps_anomaly()
            
            return True
        
        return False
    
    def _check_fps_anomaly(self):
        """检测帧率异常"""
        min_fps = self.target_fps * self.low_fps_threshold
        
        if self.current_fps < min_fps:
            if not self._low_fps_warned:
                logger.warning(
                    f"⚠️ 帧率过低: {self.current_fps} FPS "
                    f"(目标: {self.target_fps} FPS)"
                )
                self._low_fps_warned = True
        else:
            # 恢复正常，重置告警状态
            if self._low_fps_warned:
                logger.info(f"✅ 帧率已恢复正常: {self.current_fps} FPS")
                self._low_fps_warned = False
    
    def get_stats(self) -> dict:
        """
        获取统计信息
        
        Returns:
            dict: 包含 FPS、帧数等信息
        """
        return {
            'current_fps': self.current_fps,
            'target_fps': self.target_fps,
            'frame_count': self.frame_count,
            'fps_ratio': self.current_fps / self.target_fps if self.target_fps > 0 else 0
        }
    
    def reset(self):
        """重置统计信息"""
        self.frame_count = 0
        self.fps_counter = 0
        self.current_fps = 0
        self.last_fps_check = time.time()
        self._low_fps_warned = False
        logger.info("性能监控器已重置")
