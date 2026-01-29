"""
detector 模块
AI检测器包（Pipeline架构）

使用示例：
    from modules.detector import AIDetectorProcess
    
    detector = AIDetectorProcess(ipc_client, shared_state, config)
    detector.run()
"""

from .process import AIDetectorProcess

__all__ = ['AIDetectorProcess']
