"""
继电器效果实现
"""

import time
from .base import EffectBase


class RelayBlinkEffect(EffectBase):
    """继电器闪烁效果"""
    
    def __init__(self, interval: float = 0.5):
        """
        Args:
            interval: 闪烁间隔（秒）
        """
        super().__init__("RelayBlink")
        self.interval = interval
        self._last_toggle = 0
        self._state = False
    
    def start(self):
        """启动效果"""
        self._is_running = True
        self._last_toggle = time.time()
        self._state = False
    
    def update(self):
        """更新闪烁状态"""
        if not self._is_running:
            return None
        
        current_time = time.time()
        if current_time - self._last_toggle >= self.interval:
            self._state = not self._state
            self._last_toggle = current_time
        
        return self._state
    
    def stop(self):
        """停止效果"""
        self._is_running = False
        self._state = False
