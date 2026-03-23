"""
共享状态管理器 - 封装对 shared_state 的访问

提供类型安全的接口来访问和修改跨进程共享状态
"""

import multiprocessing as mp
import time
from typing import Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from utils.config import ConfigManager


class SharedStateManager:
    """
    共享状态管理器
    
    封装对 multiprocessing.Manager().dict() 的访问，
    提供类型安全和语义清晰的接口
    """
    
    # 全局状态常量
    STATE_SAFE = "safe"      # 安全状态（绿灯）
    STATE_ALERT = "alert"    # 警戒状态（黄灯）
    STATE_ALARM = "alarm"    # 报警状态（红灯闪烁）
    
    def __init__(self, config_manager: 'ConfigManager', initial_armed: bool = False):
        """
        初始化共享状态管理器
        
        Args:
            config_manager: ConfigManager 实例
            initial_armed: 初始布防状态
        """
        alarm_auto_reset_seconds = config_manager.supervisor.alarm_auto_reset_seconds or 0
        
        self._state = mp.Manager().dict({
            'global_state': self.STATE_SAFE,
            'device_id': config_manager.device.id,
            'is_streaming': False,
            'last_heartbeat': {},
            'start_time': time.time(),  # 启动时间，用于计算 uptime
            'alarm_until': 0.0,
            'alarm_auto_reset_seconds': alarm_auto_reset_seconds,
            'is_armed': initial_armed,
        })
    
    @property
    def state(self):
        """获取底层状态字典（向后兼容）"""
        return self._state
    
    # ==================== 全局状态管理 ====================
    
    def get_global_state(self) -> str:
        """获取全局状态"""
        return self._state.get('global_state', self.STATE_SAFE)
    
    def set_global_state(self, state: str) -> None:
        """
        设置全局状态
        
        Args:
            state: 状态值（STATE_SAFE, STATE_ALERT, STATE_ALARM）
        """
        if state not in (self.STATE_SAFE, self.STATE_ALERT, self.STATE_ALARM):
            raise ValueError(f"Invalid state: {state}")
        self._state['global_state'] = state
    
    def is_safe(self) -> bool:
        """检查是否处于安全状态"""
        return self.get_global_state() == self.STATE_SAFE
    
    def is_alert(self) -> bool:
        """检查是否处于警戒状态"""
        return self.get_global_state() == self.STATE_ALERT
    
    def is_alarm(self) -> bool:
        """检查是否处于报警状态"""
        return self.get_global_state() == self.STATE_ALARM
    
    # ==================== 报警管理 ====================
    
    def set_alarm_until(self, timestamp: float) -> None:
        """
        设置报警持续到指定时间戳
        
        Args:
            timestamp: 报警结束时间戳
        """
        self._state['alarm_until'] = timestamp
    
    def get_alarm_until(self) -> float:
        """获取报警结束时间戳"""
        return float(self._state.get('alarm_until', 0) or 0)
    
    def clear_alarm(self) -> None:
        """清除报警状态"""
        self._state['alarm_until'] = 0
    
    def get_alarm_auto_reset_seconds(self) -> float:
        """获取报警自动恢复秒数"""
        return float(self._state.get('alarm_auto_reset_seconds', 0) or 0)
    
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
        
        heartbeats = dict(self._state.get('last_heartbeat', {}))
        heartbeats[process_name] = timestamp
        self._state['last_heartbeat'] = heartbeats
    
    def get_last_heartbeat(self, process_name: str) -> Optional[float]:
        """
        获取进程最后心跳时间
        
        Args:
            process_name: 进程名称
            
        Returns:
            心跳时间戳，如果不存在返回 None
        """
        return self._state.get('last_heartbeat', {}).get(process_name)
    
    def get_all_heartbeats(self) -> Dict[str, float]:
        """获取所有进程的心跳时间"""
        return dict(self._state.get('last_heartbeat', {}))
    
    # ==================== 设备信息 ====================
    
    def get_device_id(self) -> str:
        """获取设备 ID"""
        return self._state.get('device_id', '')
    
    def get_start_time(self) -> float:
        """获取系统启动时间戳"""
        return self._state.get('start_time', time.time())
    
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
        self._state['is_streaming'] = is_streaming
    
    def is_streaming(self) -> bool:
        """检查是否正在推流"""
        return self._state.get('is_streaming', False)

    # ==================== 布防/撤防管理 ====================

    def set_armed(self, armed: bool) -> None:
        """设置布防/撤防状态（仅 Supervisor 调用）"""
        self._state['is_armed'] = armed

    def get_armed(self) -> bool:
        """读取布防/撤防状态"""
        return bool(self._state.get('is_armed', True))

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
