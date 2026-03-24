"""
VigiDoor 核心架构层
提供系统基础设施和核心组件
"""

__version__ = "2.0.0"

from .state import GlobalState, StateKey

__all__ = ["GlobalState", "StateKey"]
