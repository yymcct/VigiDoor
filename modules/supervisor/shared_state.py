"""
共享状态管理器 - 封装对 shared_state 的访问

提供类型安全的接口来访问和修改跨进程共享状态
"""

import multiprocessing as mp
import time
from typing import Dict, Optional, TYPE_CHECKING

from core.state import GlobalState, StateKey

if TYPE_CHECKING:
    from utils.config import ConfigManager


class SharedStateManager:
    """
    共享状态管理器
    
    封装对 multiprocessing.Manager().dict() 的访问，
    提供类型安全和语义清晰的接口
    """
    
    # 全局状态常量（向后兼容别名）
    STATE_SAFE = GlobalState.SAFE
    STATE_ALERT = GlobalState.ALERT
    STATE_ALARM = GlobalState.ALARM
    
    def __init__(self, config_manager: 'ConfigManager', initial_armed: bool = False):
        """
        初始化共享状态管理器
        
        Args:
            config_manager: ConfigManager 实例
            initial_armed: 初始布防状态
        """
        alarm_auto_reset_seconds = config_manager.supervisor.alarm_auto_reset_seconds or 0
        
        self._state = mp.Manager().dict({
            StateKey.GLOBAL_STATE: GlobalState.SAFE,
            StateKey.DEVICE_ID: config_manager.device.id,
            StateKey.IS_STREAMING: False,
            StateKey.LAST_HEARTBEAT: {},
            StateKey.START_TIME: time.time(),  # 启动时间，用于计算 uptime
            StateKey.ALARM_UNTIL: 15.0,
            StateKey.ALARM_AUTO_RESET_SECONDS: alarm_auto_reset_seconds,
            StateKey.IS_ARMED: initial_armed,
        })
    
    @property
    def state(self):
        """获取底层状态字典（向后兼容）"""
        return self._state
    
    # ==================== 全局状态管理 ====================
    
    def get_global_state(self) -> GlobalState:
        """获取全局状态"""
        return GlobalState(self._state.get(StateKey.GLOBAL_STATE, GlobalState.SAFE))
    
    def set_global_state(self, state: GlobalState) -> None:
        """
        设置全局状态
        
        Args:
            state: 状态值（GlobalState.SAFE / ALERT / ALARM）
        """
        self._state[StateKey.GLOBAL_STATE] = GlobalState(state)
    
    def is_safe(self) -> bool:
        """检查是否处于安全状态"""
        return self.get_global_state() == GlobalState.SAFE
    
    def is_alert(self) -> bool:
        """检查是否处于警戒状态"""
        return self.get_global_state() == GlobalState.ALERT
    
    def is_alarm(self) -> bool:
        """检查是否处于报警状态"""
        return self.get_global_state() == GlobalState.ALARM
    
    # ==================== 报警管理 ====================
    
    def set_alarm_until(self, timestamp: float) -> None:
        """
        设置报警持续到指定时间戳
        
        Args:
            timestamp: 报警结束时间戳
        """
        self._state[StateKey.ALARM_UNTIL] = timestamp
    
    def get_alarm_until(self) -> float:
        """获取报警结束时间戳"""
        return float(self._state.get(StateKey.ALARM_UNTIL, 0) or 0)
    
    def clear_alarm(self) -> None:
        """清除报警状态"""
        self._state[StateKey.ALARM_UNTIL] = 0
    
    def get_alarm_auto_reset_seconds(self) -> float:
        """获取报警自动恢复秒数"""
        return float(self._state.get(StateKey.ALARM_AUTO_RESET_SECONDS, 0) or 0)
    
    # ==================== 心跳管理 ====================
    
    def update_heartbeat(self, process_name: str, timestamp: Optional[float] = None) -> None:
        """
        更新进程心跳时间戳
        
        Args:
            process_name: 进程名称
            timestamp: 时间戳（默认使用当前时间）
        """
        if timestamp is None:
            timestamp = time.time()
        
        heartbeats = dict(self._state.get(StateKey.LAST_HEARTBEAT, {}))
        heartbeats[process_name] = timestamp
        self._state[StateKey.LAST_HEARTBEAT] = heartbeats
    
    def get_last_heartbeat(self, process_name: str) -> Optional[float]:
        """
        获取进程最后心跳时间
        
        Args:
            process_name: 进程名称
            
        Returns:
            心跳时间戳，如果不存在返回 None
        """
        return self._state.get(StateKey.LAST_HEARTBEAT, {}).get(process_name)
    
    def get_all_heartbeats(self) -> Dict[str, float]:
        """获取所有进程的心跳时间"""
        return dict(self._state.get(StateKey.LAST_HEARTBEAT, {}))
    
    # ==================== 设备信息 ====================
    
    def get_device_id(self) -> str:
        """获取设备 ID"""
        return self._state.get(StateKey.DEVICE_ID, '')
    
    def get_start_time(self) -> float:
        """获取系统启动时间戳"""
        return self._state.get(StateKey.START_TIME, time.time())
    
    def get_uptime(self) -> float:
        """获取系统运行时间（秒）"""
        return time.time() - self.get_start_time()
    
    # ==================== 流媒体状态 ====================
    
    def set_streaming(self, is_streaming: bool) -> None:
        """
        设置流媒体状态
        
        Args:
            is_streaming: 是否正在推流
        """
        self._state[StateKey.IS_STREAMING] = is_streaming
    
    def is_streaming(self) -> bool:
        """检查是否正在推流"""
        return self._state.get(StateKey.IS_STREAMING, False)

    # ==================== 布防/撤防管理 ====================

    def set_armed(self, armed: bool) -> None:
        """设置布防/撤防状态（仅 Supervisor 调用）"""
        self._state[StateKey.IS_ARMED] = armed

    def get_armed(self) -> bool:
        """读取布防/撤防状态"""
        return bool(self._state.get(StateKey.IS_ARMED, True))

    # ==================== 通用访问 ====================
    
    def get(self, key: str, default=None):
        """通用 get 方法（向后兼容）"""
        return self._state.get(key, default)
    
    def set(self, key: str, value):
        """通用 set 方法（向后兼容）"""
        self._state[key] = value
    
    def __getitem__(self, key):
        """支持字典式访问（向后兼容）"""
        return self._state[key]
    
    def __setitem__(self, key, value):
        """支持字典式赋值（向后兼容）"""
        self._state[key] = value
