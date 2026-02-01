"""
音频处理进程入口
简化版：调用 modules.audio.process.AudioProcess
"""

from utils.logger import setup_logger
from core.ipc import IPCClient
from modules.audio import AudioProcess

logger = setup_logger('audio_processor')


class AudioProcessorProcess:
    """
    音频处理进程入口（兼容性包装器）
    实际功能由 modules.audio.AudioProcess 实现
    """
    
    def __init__(self, ipc_client: IPCClient, shared_state, config):
        """
        初始化音频处理进程
        
        Args:
            ipc_client: IPC 客户端
            shared_state: 共享状态
            config: 配置字典
        """
        # 创建新的 AudioProcess 实例
        self.audio_process = AudioProcess(ipc_client, shared_state, config)
        
        logger.info("音频处理进程入口初始化完成（使用新架构）")
    
    def run(self):
        """启动音频处理进程"""
        # 委托给新的 AudioProcess
        self.audio_process.run()
