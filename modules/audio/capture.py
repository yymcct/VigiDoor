"""
音频采集管理器
在独立线程中持续采集麦克风音频
"""

import time
import threading
import numpy as np
from collections import deque
from typing import Optional, Callable
from utils.logger import setup_logger

logger = setup_logger('audio_capture')


class AudioCaptureManager:
    """
    音频采集管理器
    
    功能：
    1. 在独立线程中持续采集麦克风音频
    2. 使用环形缓冲区保存最近N秒音频
    3. 提供回调机制通知新数据
    
    参数：
    - sample_rate: 采样率（Hz），YamNet 要求 16000
    - channels: 声道数，单声道=1
    - chunk_duration: 每次采集的音频块时长（秒）
    - buffer_duration: 环形缓冲区保存的时长（秒）
    """
    
    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        chunk_duration: float = 0.1,
        buffer_duration: float = 10.0
    ):
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_duration = chunk_duration
        self.chunk_size = int(sample_rate * chunk_duration)
        self.buffer_duration = buffer_duration
        
        # 环形缓冲区（保存最近10秒）
        max_chunks = int(buffer_duration / chunk_duration)
        self.buffer = deque(maxlen=max_chunks)
        self.buffer_lock = threading.Lock()
        
        # 回调函数列表
        self.callbacks = []
        
        # 线程控制
        self.running = False
        self.thread = None
        
        # sounddevice 实例
        self.stream = None
        
        logger.info(f"音频采集管理器初始化")
        logger.info(f"  采样率: {sample_rate} Hz")
        logger.info(f"  声道数: {channels}")
        logger.info(f"  块大小: {self.chunk_size} samples")
        logger.info(f"  缓冲时长: {buffer_duration}s")
    
    def register_callback(self, callback: Callable[[np.ndarray], None]) -> None:
        """
        注册新数据回调函数
        
        Args:
            callback: 回调函数，接收音频块 (float32 NumPy数组)
        """
        self.callbacks.append(callback)
        logger.debug(f"注册回调函数: {callback.__name__}")
    
    def start(self) -> bool:
        """启动采集线程"""
        if self.running:
            logger.warning("采集线程已在运行")
            return False
        
        try:
            # 初始化 sounddevice
            import sounddevice as sd

            self.stream = sd.InputStream(
                samplerate=16000,
                channels=2,
                dtype="float32",
                blocksize=self.chunk_size,
                device="seedsnoop_plug",
                callback=self._audio_callback
            )
            
            # 启动线程
            self.running = True
            self.thread = threading.Thread(target=self._run, daemon=True, name="AudioCapture")
            self.thread.start()
            
            self.stream.start()
            logger.info("✅ 音频采集线程已启动")
            return True
            
        except ImportError:
            logger.error("sounddevice 未安装，无法启动音频采集")
            return False
        except Exception as e:
            logger.error(f"启动音频采集失败: {e}", exc_info=True)
            return False
    
    def _audio_callback(self, in_data, frames, time_info, status):
        """sounddevice 回调函数"""
        if status:
            logger.warning(f"音频流状态: {status}")

        audio_chunk = np.asarray(in_data, dtype=np.float32).reshape(-1)
        
        # 保存到环形缓冲区
        with self.buffer_lock:
            self.buffer.append((time.time(), audio_chunk))
        
        # 触发回调
        for callback in self.callbacks:
            try:
                callback(audio_chunk)
            except Exception as e:
                logger.error(f"回调函数异常: {e}")
        
        return None
    
    def _run(self):
        """采集线程主循环（PyAudio 使用回调，此处仅保持线程活跃）"""
        logger.info("采集线程运行中...")
        while self.running:
            time.sleep(0.5)
    
    # ...已移除模拟音频生成相关方法...
    
    def get_latest_chunk(self) -> Optional[np.ndarray]:
        """获取最新的音频块"""
        with self.buffer_lock:
            if len(self.buffer) > 0:
                return self.buffer[-1][1].copy()
        return None
    
    def get_buffer_window(self, duration: float = 1.0) -> Optional[np.ndarray]:
        """
        获取最近N秒的音频数据
        
        Args:
            duration: 时长（秒）
            
        Returns:
            拼接的音频数组，或 None
        """
        with self.buffer_lock:
            if len(self.buffer) == 0:
                return None
            
            # 计算需要的块数
            num_chunks = int(duration / self.chunk_duration)
            num_chunks = min(num_chunks, len(self.buffer))
            
            # 获取最近的块
            chunks = [self.buffer[-i][1] for i in range(num_chunks, 0, -1)]
            
            # 拼接
            return np.concatenate(chunks)
    
    def stop(self):
        """停止采集线程"""
        if not self.running:
            return
        
        logger.info("正在停止音频采集...")
        self.running = False
        
        # 等待线程结束
        if self.thread:
            self.thread.join(timeout=2.0)
        
        # 关闭音频流
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except:
                pass
        
        logger.info("✅ 音频采集已停止")
    
    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self.running and (self.thread is not None) and self.thread.is_alive()
