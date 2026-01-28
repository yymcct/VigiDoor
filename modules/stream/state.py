"""
推流状态管理模块
"""

from enum import Enum
from utils.logger import setup_logger

logger = setup_logger('stream_state')


class StreamState(Enum):
    """推流状态机"""
    IDLE = "idle"            # 空闲
    STARTING = "starting"    # 启动中
    STREAMING = "streaming"  # 推流中
    STOPPING = "stopping"    # 停止中


class StateManager:
    """
    推流状态管理器
    
    负责管理推流状态转换，提供状态验证和日志
    """
    
    def __init__(self):
        self._state = StreamState.IDLE
        
        # 定义合法的状态转换
        self._transitions = {
            StreamState.IDLE: [StreamState.STARTING],
            StreamState.STARTING: [StreamState.STREAMING, StreamState.IDLE],
            StreamState.STREAMING: [StreamState.STOPPING],
            StreamState.STOPPING: [StreamState.IDLE],
        }
    
    @property
    def state(self) -> StreamState:
        """获取当前状态"""
        return self._state
    
    def can_transition_to(self, new_state: StreamState) -> bool:
        """
        检查是否可以转换到新状态
        
        Args:
            new_state: 目标状态
            
        Returns:
            bool: 如果转换合法返回 True
        """
        return new_state in self._transitions.get(self._state, [])
    
    def transition_to(self, new_state: StreamState) -> bool:
        """
        转换到新状态
        
        Args:
            new_state: 目标状态
            
        Returns:
            bool: 转换成功返回 True
        """
        if not self.can_transition_to(new_state):
            logger.warning(
                f"❌ 非法状态转换: {self._state.value} → {new_state.value}"
            )
            return False
        
        old_state = self._state
        self._state = new_state
        
        logger.info(f"🔄 状态转换: {old_state.value} → {new_state.value}")
        return True
    
    def is_idle(self) -> bool:
        """是否处于空闲状态"""
        return self._state == StreamState.IDLE
    
    def is_streaming(self) -> bool:
        """是否正在推流"""
        return self._state == StreamState.STREAMING
    
    def is_active(self) -> bool:
        """是否处于活跃状态（非空闲）"""
        return self._state != StreamState.IDLE
    
    def reset(self):
        """重置为空闲状态"""
        if self._state != StreamState.IDLE:
            logger.info(f"🔄 强制重置状态: {self._state.value} → idle")
            self._state = StreamState.IDLE
