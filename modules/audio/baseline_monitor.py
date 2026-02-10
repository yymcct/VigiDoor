"""
环境噪音基线学习器
动态学习和更新环境音量基线
"""

import time
import numpy as np
from collections import deque
from utils.logger import setup_logger

logger = setup_logger('baseline_monitor')


class EnvironmentBaselineMonitor:
    """
    环境噪音基线学习器
    
    功能：
    1. 统计最近N分钟的音量数据
    2. 计算基线音量和标准差
    3. 过滤异常值（使用四分位法IQR）
    4. 动态更新基线（使用EMA平滑）
    
    参数：
    - learning_window_minutes: 初始学习窗口（分钟）
    - update_window_seconds: 基线更新间隔（秒）
    - outlier_threshold_iqr: 异常值过滤阈值（IQR倍数）
    - update_alpha: EMA更新速率（0-1）
    """
    
    def __init__(
        self,
        learning_window_minutes: float = 5.0,
        update_window_seconds: float = 30.0,
        outlier_threshold_iqr: float = 1.5,
        update_alpha: float = 0.1
    ):
        self.learning_window_minutes = learning_window_minutes
        self.update_window_seconds = update_window_seconds
        self.outlier_threshold_iqr = outlier_threshold_iqr
        self.update_alpha = update_alpha
        
        # 学习期数据缓冲（保存dB值）
        self.learning_buffer = deque(maxlen=int(learning_window_minutes * 60 * 10))  # 假设每100ms一个样本
        
        # 更新期数据缓冲（保存最近30秒的样本）
        self.update_buffer = deque(maxlen=int(update_window_seconds * 10))
        
        # 基线状态
        self.baseline_db = None  # 基线音量（dB）
        self.baseline_std = None  # 标准差（dB）
        self.is_ready = False  # 是否完成初始学习
        
        # 时间控制
        self.start_time = time.time()
        self.last_update_time = 0.0
        
        # 统计
        self.sample_count = 0
        self.update_count = 0
        
        # 污染保护：报警期间不更新基线
        self.is_alarm_active = False
        
        logger.info(f"环境基线学习器初始化")
        logger.info(f"  学习窗口: {learning_window_minutes} 分钟")
        logger.info(f"  更新间隔: {update_window_seconds} 秒")
        logger.info(f"  异常值阈值: {outlier_threshold_iqr} IQR")
        logger.info(f"  更新速率: {update_alpha}")
    
    def add_sample(self, db_value: float):
        """
        添加音量样本
        
        Args:
            db_value: 音量分贝值
        """
        self.sample_count += 1
        
        # 学习期：收集数据
        if not self.is_ready:
            self.learning_buffer.append(db_value)
            
            # 检查是否达到学习时长
            elapsed = time.time() - self.start_time
            if elapsed >= self.learning_window_minutes * 60:
                self._finish_learning()
        
        # 运行期：动态更新
        else:
            # 报警期间不添加样本（避免污染基线）
            if not self.is_alarm_active:
                self.update_buffer.append(db_value)
            
            # 检查是否需要更新基线
            current_time = time.time()
            if current_time - self.last_update_time >= self.update_window_seconds:
                self._update_baseline()
                self.last_update_time = current_time
    
    def _finish_learning(self):
        """完成初始学习，计算基线"""
        if len(self.learning_buffer) < 10:
            logger.warning("学习期样本不足，延长学习时间")
            return
        
        # 过滤异常值
        samples = np.array(self.learning_buffer)
        filtered_samples = self._filter_outliers(samples)
        
        if len(filtered_samples) < 5:
            logger.warning("过滤后样本不足，使用原始数据")
            filtered_samples = samples
        
        # 计算初始基线
        self.baseline_db = float(np.median(filtered_samples))
        self.baseline_std = float(np.std(filtered_samples))
        self.is_ready = True
        
        logger.info(f"✅ 基线学习完成")
        logger.info(f"  基线音量: {self.baseline_db:.1f} dB")
        logger.info(f"  标准差: {self.baseline_std:.1f} dB")
        logger.info(f"  样本数: {len(filtered_samples)} / {len(samples)}")
        
        # 清空学习缓冲，释放内存
        self.learning_buffer.clear()
    
    def _update_baseline(self):
        """动态更新基线（使用EMA）"""
        if len(self.update_buffer) < 5:
            return  # 样本不足，跳过更新
        
        # 过滤异常值
        samples = np.array(self.update_buffer)
        filtered_samples = self._filter_outliers(samples)
        
        if len(filtered_samples) < 3:
            return  # 过滤后样本太少
        
        # 计算新基线
        new_baseline = float(np.median(filtered_samples))
        new_std = float(np.std(filtered_samples))
        
        # EMA平滑更新
        old_baseline = self.baseline_db
        self.baseline_db = self.update_alpha * new_baseline + (1 - self.update_alpha) * self.baseline_db
        self.baseline_std = self.update_alpha * new_std + (1 - self.update_alpha) * self.baseline_std
        
        self.update_count += 1
        
        # 记录显著变化
        delta = abs(self.baseline_db - old_baseline)
        if delta > 5.0:
            logger.info(f"📊 基线更新: {old_baseline:.1f} → {self.baseline_db:.1f} dB (Δ{delta:+.1f})")
        else:
            logger.debug(f"基线更新: {self.baseline_db:.1f} dB (Std: {self.baseline_std:.1f})")
        
        # 清空更新缓冲
        self.update_buffer.clear()
    
    def _filter_outliers(self, samples: np.ndarray) -> np.ndarray:
        """
        使用四分位法（IQR）过滤异常值
        
        Args:
            samples: 音量样本数组
            
        Returns:
            过滤后的样本
        """
        if len(samples) < 4:
            return samples
        
        # 计算四分位数
        q1 = np.percentile(samples, 25)
        q3 = np.percentile(samples, 75)
        iqr = q3 - q1
        
        # 定义异常值边界
        lower_bound = q1 - self.outlier_threshold_iqr * iqr
        upper_bound = q3 + self.outlier_threshold_iqr * iqr
        
        # 过滤
        mask = (samples >= lower_bound) & (samples <= upper_bound)
        filtered = samples[mask]
        
        removed_count = len(samples) - len(filtered)
        if removed_count > 0:
            logger.debug(f"异常值过滤: 移除 {removed_count} 个样本 ({removed_count/len(samples)*100:.1f}%)")
        
        return filtered
    
    def set_alarm_state(self, is_alarm: bool):
        """
        设置报警状态（报警期间不更新基线）
        
        Args:
            is_alarm: 是否处于报警状态
        """
        if is_alarm and not self.is_alarm_active:
            logger.info("🚨 报警激活，暂停基线更新")
        elif not is_alarm and self.is_alarm_active:
            logger.info("✅ 报警解除，恢复基线更新")
        
        self.is_alarm_active = is_alarm
    
    def get_baseline_info(self) -> dict:
        """获取基线信息"""
        return {
            'is_ready': self.is_ready,
            'baseline_db': self.baseline_db,
            'baseline_std': self.baseline_std,
            'sample_count': self.sample_count,
            'update_count': self.update_count,
            'is_alarm_active': self.is_alarm_active
        }
    
    def reset(self):
        """重置基线学习器（重新学习）"""
        logger.info("🔄 重置基线学习器，开始重新学习")
        
        self.learning_buffer.clear()
        self.update_buffer.clear()
        self.baseline_db = None
        self.baseline_std = None
        self.is_ready = False
        self.start_time = time.time()
        self.last_update_time = 0.0
        self.sample_count = 0
        self.update_count = 0
        self.is_alarm_active = False
