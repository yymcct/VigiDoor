"""
效果系统
用于 LED 动画、蜂鸣器节奏等
"""

from .base import EffectBase
from .led_effects import (
    SolidColorEffect,
    BlinkEffect,
    BreathEffect,
    RainbowEffect,
    PulseEffect
)
from .buzzer_effects import (
    BeepEffect,
    BeepPatternEffect,
    SirenEffect,
    MorseCodeEffect,
    ChirpEffect
)

__all__ = [
    'EffectBase',
    # LED 效果
    'SolidColorEffect',
    'BlinkEffect',
    'BreathEffect',
    'RainbowEffect',
    'PulseEffect',
    # 蜂鸣器效果
    'BeepEffect',
    'BeepPatternEffect',
    'SirenEffect',
    'MorseCodeEffect',
    'ChirpEffect'
]
