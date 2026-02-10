"""
音量突变检测器
基于环境基线的音量异常检测
"""

import time
import numpy as np
from enum import Enum
from utils.logger import setup_logger

logger = setup_logger('volume_anomaly')


class AlarmLevel(Enum):
    """报警级别"""
    NORMAL = "NORMAL"
    ALERT = "ALERT"
    ALARM = "ALARM"


class VolumeAnomalyDetector:
    """
    音量突变检测器
    
    功能：
    1. 计算音频的 RMS 音量和分贝值
    2. 与环境基线对比，计算音量偏差
    3. 多级阈值判定（警戒/报警）
    4. 持续时长检测（避免瞬时噪音）
    5. 防抖机制（报警冷却）
    
    参数：
    - alert_threshold_db: 警戒阈值（相对基线，dB）
    - alarm_threshold_db: 报警阈值（相对基线，dB）
    - duration_threshold_seconds: 持续时长要求（秒）
    - cooldown_seconds: 报警冷却时间（秒）
    - reference_level: 参考电平，用于计算 dB
    """
    
    def __init__(
        self,
        alert_threshold_db: float = 10.0,
        alarm_threshold_db: float = 20.0,
        duration_threshold_seconds: float = 0.5,
        cooldown_seconds: float = 10.0,
        reference_level: float = 1.0
    ):
        self.alert_threshold_db = alert_threshold_db
        self.alarm_threshold_db = alarm_threshold_db
        self.duration_threshold_seconds = duration_threshold_seconds
        self.cooldown_seconds = cooldown_seconds
        self.reference_level = reference_level
        
        # 持续时长检测
        self.alert_start_time = None
        self.alarm_start_time = None
        
        # 防抖控制
        self.last_alarm_time = 0.0
        
        # 当前状态
        self.current_level = AlarmLevel.NORMAL
        
        # 统计
        self.total_checks = 0
        self.alert_count = 0
        self.alarm_count = 0
        
        logger.info(f"音量突变检测器初始化")
        logger.info(f"  警戒阈值: +{alert_threshold_db} dB (相对基线)")
        logger.info(f"  报警阈值: +{alarm_threshold_db} dB (相对基线)")
        logger.info(f"  持续时长: {duration_threshold_seconds} 秒")
        logger.info(f"  冷却时间: {cooldown_seconds} 秒")
    
    def analyze(
        self, 
        audio_chunk: np.ndarray, 
        baseline_db: float = None
    ) -> tuple[AlarmLevel, float, float]:
        """
        分析音频块，判断是否有音量异常
        
        Args:
            audio_chunk: 音频数据 (float32 NumPy数组)
            baseline_db: 环境基线音量（dB），如果为None则跳过检测
            
        Returns:
            (报警级别, 当前音量dB, 偏差dB)
        """
        self.total_checks += 1
        
        # 计算当前音量
        current_db = self._calculate_db(audio_chunk)
        
        # 基线未就绪，跳过检测
        if baseline_db is None:
            return AlarmLevel.NORMAL, current_db, 0.0
        
        # 计算偏差
        delta_db = current_db - baseline_db
        
        # 多级判定
        current_time = time.time()
        
        # 报警级别判定
        if delta_db >= self.alarm_threshold_db:
            # 检查冷却期
            if current_time - self.last_alarm_time < self.cooldown_seconds:
                logger.debug(f"音量异常 {delta_db:+.1f}dB，但在冷却期内")
                return AlarmLevel.NORMAL, current_db, delta_db
            
            # 持续时长检测
            if self.alarm_start_time is None:
                self.alarm_start_time = current_time
                logger.debug(f"⚠️  检测到音量突变 {delta_db:+.1f}dB，开始持续检测 {self.duration_threshold_seconds}")
                return AlarmLevel.NORMAL, current_db, delta_db
            
            duration = current_time - self.alarm_start_time
            if duration >= self.duration_threshold_seconds:
                # 触发报警
                self.current_level = AlarmLevel.ALARM
                self.last_alarm_time = current_time
                self.alarm_count += 1
                self.alarm_start_time = None  # 重置
                
                logger.warning(
                    f"🚨 音量报警触发: {current_db:.1f}dB "
                    f"(基线: {baseline_db:.1f}dB, 偏差: {delta_db:+.1f}dB, "
                    f"持续: {duration:.1f}s)"
                )
                
                return AlarmLevel.ALARM, current_db, delta_db
        
        # 警戒级别判定
        elif delta_db >= self.alert_threshold_db:
            if self.alert_start_time is None:
                self.alert_start_time = current_time
            
            duration = current_time - self.alert_start_time
            if duration >= self.duration_threshold_seconds:
                self.current_level = AlarmLevel.ALERT
                self.alert_count += 1
                
                logger.info(
                    f"⚠️  音量警戒: {current_db:.1f}dB "
                    f"(基线: {baseline_db:.1f}dB, 偏差: {delta_db:+.1f}dB)"
                )
                
                return AlarmLevel.ALERT, current_db, delta_db
            
            # 未满足持续时长
            return AlarmLevel.NORMAL, current_db, delta_db
        
        # 正常级别
        else:
            # 重置持续时长计时
            self.alarm_start_time = None
            self.alert_start_time = None
            self.current_level = AlarmLevel.NORMAL
            
            return AlarmLevel.NORMAL, current_db, delta_db
    
    def _calculate_db(self, audio_chunk: np.ndarray) -> float:
        """
        计算音频的分贝值
        
        Args:
            audio_chunk: 音频数据
            
        Returns:
            分贝值 (dB)
        """
        # 计算 RMS
        rms = np.sqrt(np.mean(audio_chunk ** 2))
        rms = max(rms, 1e-10)  # 避免 log(0)
        
        # 转换为分贝
        db = 20 * np.log10(rms / self.reference_level)
        return db
    
    def get_statistics(self) -> dict:
        """获取统计信息"""
        alarm_rate = self.alarm_count / max(self.total_checks, 1) * 100
        alert_rate = self.alert_count / max(self.total_checks, 1) * 100
        
        return {
            'total_checks': self.total_checks,
            'alert_count': self.alert_count,
            'alarm_count': self.alarm_count,
            'alert_rate': f"{alert_rate:.2f}%",
            'alarm_rate': f"{alarm_rate:.2f}%",
            'current_level': self.current_level.value,
            'alert_threshold_db': self.alert_threshold_db,
            'alarm_threshold_db': self.alarm_threshold_db
        }
    
    def reset_statistics(self):
        """重置统计信息"""
        self.total_checks = 0
        self.alert_count = 0
        self.alarm_count = 0
        logger.info("统计信息已重置")
