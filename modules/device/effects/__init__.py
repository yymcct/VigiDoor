"""
效果系统
用于 LED 动画
"""

from .base import EffectBase
from .led_effects import (
    SolidColorEffect,
    BlinkEffect,
    BreathEffect,
    RainbowEffect,
    PulseEffect
)
__all__ = [
    'EffectBase',
    # LED 效果
    'SolidColorEffect',
    'BlinkEffect',
    'BreathEffect',
    'RainbowEffect',
    'PulseEffect'
]
