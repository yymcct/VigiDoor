"""
音量监控器
实时监控音频分贝，决定是否触发 YamNet 检测
"""

import time
import numpy as np
from utils.logger import setup_logger

logger = setup_logger('volume_monitor')


class VolumeMonitor:
    """
    音量监控器
    
    功能：
    1. 计算音频的 RMS 音量和分贝值
    2. 根据阈值判断是否需要触发 YamNet 检测
    3. 防抖逻辑，避免频繁触发
    
    参数：
    - threshold_db: 触发阈值（分贝），推荐 50-60 dB
    - debounce_seconds: 防抖时长（秒），两次触发之间的最小间隔
    - reference_level: 参考电平，用于计算 dB
    """
    
    def __init__(
        self,
        threshold_db: float = 55.0,
        debounce_seconds: float = 2.0,
        reference_level: float = 1.0
    ):
        self.threshold_db = threshold_db
        self.debounce_seconds = debounce_seconds
        self.reference_level = reference_level
        
        # 防抖控制
        self.last_trigger_time = 0.0
        
        # 统计
        self.trigger_count = 0
        self.total_checks = 0
        
        logger.info(f"音量监控器初始化")
        logger.info(f"  触发阈值: {threshold_db} dB")
        logger.info(f"  防抖时长: {debounce_seconds}s")
    
    def analyze(self, audio_chunk: np.ndarray) -> tuple[bool, float]:
        """
        分析音频块，判断是否需要触发检测
        
        Args:
            audio_chunk: 音频数据 (float32 NumPy数组)
            
        Returns:
            (是否触发, 当前分贝值)
        """
        self.total_checks += 1
        
        # 计算 RMS 音量
        rms = self._calculate_rms(audio_chunk)
        
        # 转换为分贝
        db = self._rms_to_db(rms)
        
        # 判断是否超过阈值
        if db < self.threshold_db:
            return False, db
        
        # 检查防抖
        current_time = time.time()
        if current_time - self.last_trigger_time < self.debounce_seconds:
            logger.debug(f"音量 {db:.1f}dB 超阈值，但在防抖期内，跳过")
            return False, db
        
        # 触发检测
        self.last_trigger_time = current_time
        self.trigger_count += 1
        
        logger.info(f"🔊 音量触发: {db:.1f}dB (阈值: {self.threshold_db}dB)")
        
        return True, db
    
    def _calculate_rms(self, audio_chunk: np.ndarray) -> float:
        """
        计算 RMS（均方根）音量
        
        Args:
            audio_chunk: 音频数据
            
        Returns:
            RMS 值
        """
        # 计算均方根
        rms = np.sqrt(np.mean(audio_chunk ** 2))
        return max(rms, 1e-10)  # 避免 log(0)
    
    def _rms_to_db(self, rms: float) -> float:
        """
        将 RMS 转换为分贝值
        
        Args:
            rms: RMS 值
            
        Returns:
            分贝值 (dB)
        """
        db = 20 * np.log10(rms / self.reference_level)
        return db
    
    def get_statistics(self) -> dict:
        """获取统计信息"""
        trigger_rate = self.trigger_count / max(self.total_checks, 1) * 100
        
        return {
            'total_checks': self.total_checks,
            'trigger_count': self.trigger_count,
            'trigger_rate': f"{trigger_rate:.2f}%",
            'threshold_db': self.threshold_db,
            'debounce_seconds': self.debounce_seconds
        }
    
    def reset_statistics(self):
        """重置统计信息"""
        self.trigger_count = 0
        self.total_checks = 0
        logger.info("统计信息已重置")
