"""
检测策略
控制检测频率和跳帧逻辑
"""

from typing import Dict, Any
from core.state import GlobalState, StateKey
from utils.logger import setup_logger

logger = setup_logger('detection_strategy')


class DetectionStrategy:
    """
    检测策略 - 动态调整检测频率
    
    功能：
    1. 根据系统状态调整检测频率
    2. 跳帧策略（节省资源）
    3. 自适应调整
    """
    
    def __init__(self, config: dict, shared_state: dict):
        """
        Args:
            config: 检测器配置
            shared_state: 全局共享状态
        """
        self.config = config
        self.state = shared_state
        
        # 配置参数
        self.default_interval = config.get('detect_interval', 8)  # 默认每8帧检测一次
        self.safe_interval = config.get('safe_interval', 8)
        self.alert_interval = config.get('alert_interval', 3)
        self.alarm_interval = config.get('alarm_interval', 1)  # 报警时每帧都检测
        
        logger.info(
            f"检测策略初始化: safe={self.safe_interval}, "
            f"alert={self.alert_interval}, alarm={self.alarm_interval}"
        )
    
    def should_detect(self, frame_id: int) -> bool:
        """
        判断是否应该检测此帧
        
        Args:
            frame_id: 当前帧号
        
        Returns:
            bool: 是否应该检测
        """
        # 撤防状态：禁止所有 AI 检测
        if not self.state.get(StateKey.IS_ARMED, True):
            return False

        # 根据系统状态获取检测间隔
        interval = self._get_current_interval()
        
        # 每N帧检测一次
        return frame_id % interval == 0
    
    def _get_current_interval(self) -> int:
        """根据系统状态获取当前检测间隔"""
        system_state = self.state.get(StateKey.GLOBAL_STATE, GlobalState.SAFE)
        
        if system_state == GlobalState.ALARM:
            return self.alarm_interval
        elif system_state == GlobalState.ALERT:
            return self.alert_interval
        else:
            return self.safe_interval
    
    def get_stats(self) -> Dict[str, Any]:
        """获取策略统计信息"""
        return {
            'current_state': self.state.get(StateKey.GLOBAL_STATE, GlobalState.SAFE),
            'current_interval': self._get_current_interval(),
            'config': {
                'safe_interval': self.safe_interval,
                'alert_interval': self.alert_interval,
                'alarm_interval': self.alarm_interval
            }
        }
