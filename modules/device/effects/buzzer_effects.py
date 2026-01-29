"""
蜂鸣器音效实现
包含常用的蜂鸣器音效模式
"""

import time
from .base import EffectBase


class BeepEffect(EffectBase):
    """单次蜂鸣效果"""
    
    def __init__(self, duration: float = 0.1):
        """
        Args:
            duration: 蜂鸣持续时间（秒）
        """
        super().__init__("Beep")
        self.duration = duration
        self._start_time = 0
    
    def start(self):
        """启动效果"""
        self._is_running = True
        self._start_time = time.time()
    
    def update(self):
        """更新效果"""
        if not self._is_running:
            return None
        
        elapsed = time.time() - self._start_time
        
        if elapsed < self.duration:
            return True
        else:
            self._is_running = False
            return False
    
    def stop(self):
        """停止效果"""
        self._is_running = False


class BeepPatternEffect(EffectBase):
    """蜂鸣模式效果（短-短-长）"""
    
    def __init__(self, short_duration: float = 0.1, long_duration: float = 0.3, 
                 interval: float = 0.1, repeat: int = 1):
        """
        Args:
            short_duration: 短蜂鸣时长（秒）
            long_duration: 长蜂鸣时长（秒）
            interval: 蜂鸣间隔（秒）
            repeat: 重复次数
        """
        super().__init__("BeepPattern")
        self.short_duration = short_duration
        self.long_duration = long_duration
        self.interval = interval
        self.repeat = repeat
        
        self._start_time = 0
        self._current_repeat = 0
    
    def start(self):
        """启动效果"""
        self._is_running = True
        self._start_time = time.time()
        self._current_repeat = 0
    
    def update(self):
        """更新效果（短-短-长 模式）"""
        if not self._is_running:
            return None
        
        elapsed = time.time() - self._start_time
        
        # 一个周期的时间结构：
        # 短蜂鸣 -> 间隔 -> 短蜂鸣 -> 间隔 -> 长蜂鸣 -> 间隔
        cycle_duration = (self.short_duration + self.interval) * 2 + self.long_duration + self.interval
        
        cycle_position = elapsed % cycle_duration
        
        # 判断当前位置
        if cycle_position < self.short_duration:
            # 第一个短蜂鸣
            return True
        elif cycle_position < self.short_duration + self.interval:
            # 第一个间隔
            return False
        elif cycle_position < self.short_duration * 2 + self.interval:
            # 第二个短蜂鸣
            return True
        elif cycle_position < self.short_duration * 2 + self.interval * 2:
            # 第二个间隔
            return False
        elif cycle_position < self.short_duration * 2 + self.interval * 2 + self.long_duration:
            # 长蜂鸣
            return True
        else:
            # 最后间隔
            return False
        
        # 检查是否完成所有重复
        if elapsed >= cycle_duration * self.repeat:
            self._is_running = False
            return False
    
    def stop(self):
        """停止效果"""
        self._is_running = False


class SirenEffect(EffectBase):
    """警报声效果（连续蜂鸣）"""
    
    def __init__(self, on_duration: float = 0.5, off_duration: float = 0.5):
        """
        Args:
            on_duration: 开启时长（秒）
            off_duration: 关闭时长（秒）
        """
        super().__init__("Siren")
        self.on_duration = on_duration
        self.off_duration = off_duration
        self._start_time = 0
    
    def start(self):
        """启动效果"""
        self._is_running = True
        self._start_time = time.time()
    
    def update(self):
        """更新效果"""
        if not self._is_running:
            return None
        
        elapsed = time.time() - self._start_time
        cycle_duration = self.on_duration + self.off_duration
        cycle_position = elapsed % cycle_duration
        
        return cycle_position < self.on_duration
    
    def stop(self):
        """停止效果"""
        self._is_running = False


class MorseCodeEffect(EffectBase):
    """摩斯密码效果"""
    
    def __init__(self, code: str, dot_duration: float = 0.1):
        """
        Args:
            code: 摩斯密码字符串（. 为短音，- 为长音，空格为间隔）
            dot_duration: 短音时长（秒），长音为 3 倍
        """
        super().__init__("MorseCode")
        self.code = code
        self.dot_duration = dot_duration
        self.dash_duration = dot_duration * 3
        self.symbol_gap = dot_duration
        
        self._start_time = 0
        self._pattern = self._parse_code()
    
    def _parse_code(self):
        """解析摩斯密码为时间序列"""
        pattern = []
        for char in self.code:
            if char == '.':
                pattern.append((True, self.dot_duration))
                pattern.append((False, self.symbol_gap))
            elif char == '-':
                pattern.append((True, self.dash_duration))
                pattern.append((False, self.symbol_gap))
            elif char == ' ':
                pattern.append((False, self.dot_duration * 7))
        return pattern
    
    def start(self):
        """启动效果"""
        self._is_running = True
        self._start_time = time.time()
    
    def update(self):
        """更新效果"""
        if not self._is_running:
            return None
        
        elapsed = time.time() - self._start_time
        
        # 计算总时长
        total_duration = sum(duration for _, duration in self._pattern)
        
        if elapsed >= total_duration:
            self._is_running = False
            return False
        
        # 找到当前位置
        current_time = 0
        for state, duration in self._pattern:
            current_time += duration
            if elapsed < current_time:
                return state
        
        return False
    
    def stop(self):
        """停止效果"""
        self._is_running = False


class ChirpEffect(EffectBase):
    """快速短促音效（类似鸟叫）"""
    
    def __init__(self, chirp_count: int = 3, chirp_duration: float = 0.05, 
                 chirp_interval: float = 0.05):
        """
        Args:
            chirp_count: 连续鸣叫次数
            chirp_duration: 单次鸣叫时长（秒）
            chirp_interval: 鸣叫间隔（秒）
        """
        super().__init__("Chirp")
        self.chirp_count = chirp_count
        self.chirp_duration = chirp_duration
        self.chirp_interval = chirp_interval
        
        self._start_time = 0
    
    def start(self):
        """启动效果"""
        self._is_running = True
        self._start_time = time.time()
    
    def update(self):
        """更新效果"""
        if not self._is_running:
            return None
        
        elapsed = time.time() - self._start_time
        
        # 总时长
        total_duration = self.chirp_count * (self.chirp_duration + self.chirp_interval)
        
        if elapsed >= total_duration:
            self._is_running = False
            return False
        
        # 计算当前位置
        cycle_duration = self.chirp_duration + self.chirp_interval
        cycle_position = elapsed % cycle_duration
        
        return cycle_position < self.chirp_duration
    
    def stop(self):
        """停止效果"""
        self._is_running = False
