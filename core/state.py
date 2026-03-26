"""
共享状态枚举定义

定义跨进程共享状态字典的键名和值类型。
所有子进程通过 ProcessContext.shared_state 只读访问这些状态，
写操作由 Supervisor 通过 SharedStateManager 完成。
"""

from enum import Enum


class GlobalState(str, Enum):
    """全局安全状态枚举"""
    SAFE = "safe"      # 安全状态（绿灯）
    ALERT = "alert"    # 警戒状态（黄灯）
    ALARM = "alarm"    # 报警状态（红灯闪烁）


class StateKey(str, Enum):
    """共享状态字典键名枚举"""
    GLOBAL_STATE = 'global_state'
    DEVICE_ID = 'device_id'
    IS_STREAMING = 'is_streaming'
    LAST_HEARTBEAT = 'last_heartbeat'
    START_TIME = 'start_time'
    ALARM_UNTIL = 'alarm_until'
    ALARM_AUTO_RESET_SECONDS = 'alarm_auto_reset_seconds'
    ALERT_UNTIL = 'alert_until'
    ALERT_AUTO_RESET_SECONDS = 'alert_auto_reset_seconds'
    IS_ARMED = 'is_armed' # 是否处于布防状态
