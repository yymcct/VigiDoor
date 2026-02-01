"""
音频源管理器
为 Stream 进程提供音频数据
"""

import time
import threading
from typing import Optional
import numpy as np
from utils.logger import setup_logger

logger = setup_logger('audio_source')


class AudioSourceManager:
    """
    音频源管理器
    
    功能：
    1. 在 Stream 进程内启动音频采集
    2. 提供音频帧给编码器
    3. 与视频流同步
    
    注意：
    - 使用 ALSA 直接采集，由 FFmpeg 处理
    - 本类主要用于预留接口和监控
    """
    
    def __init__(self, device: str = "plughw:1,0", sample_rate: int = 16000, channels: int = 1):
        """
        初始化音频源管理器
        
        Args:
            device: ALSA 设备名称（例如：plughw:1,0 为 WM8960，使用 plughw 支持多路访问）
            sample_rate: 采样率（Hz）
            channels: 声道数
        """
        self.device = device
        self.sample_rate = sample_rate
        self.channels = channels
        
        # 状态
        self.is_active = False
        
        logger.info(f"音频源管理器初始化")
        logger.info(f"  设备: {device}")
        logger.info(f"  采样率: {sample_rate} Hz")
        logger.info(f"  声道数: {channels}")
    
    def start(self) -> bool:
        """
        启动音频源
        
        注意：实际采集由 FFmpeg 进行，此方法仅用于状态管理
        """
        if self.is_active:
            logger.warning("音频源已启动")
            return False
        
        # 验证 ALSA 设备是否存在
        if not self._check_alsa_device():
            logger.warning(f"ALSA 设备 {self.device} 不可用")
            return False
        
        self.is_active = True
        logger.info("✅ 音频源已启动（由 FFmpeg 采集）")
        return True
    
    def _check_alsa_device(self) -> bool:
        """检查 ALSA 设备是否可用"""
        try:
            import subprocess
            
            # 使用 arecord -l 列出设备
            result = subprocess.run(
                ['arecord', '-l'],
                capture_output=True,
                text=True,
                timeout=2
            )
            
            if result.returncode == 0:
                logger.debug(f"ALSA 设备列表:\n{result.stdout}")
                return True
            else:
                logger.warning("无法列出 ALSA 设备")
                return False
                
        except FileNotFoundError:
            logger.warning("arecord 未安装")
            return False
        except Exception as e:
            logger.warning(f"检查 ALSA 设备失败: {e}")
            return False
    
    def stop(self):
        """停止音频源"""
        if not self.is_active:
            return
        
        self.is_active = False
        logger.info("✅ 音频源已停止")
    
    def get_device_name(self) -> str:
        """获取设备名称"""
        return self.device
    
    def get_sample_rate(self) -> int:
        """获取采样率"""
        return self.sample_rate
    
    def get_channels(self) -> int:
        """获取声道数"""
        return self.channels
