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
        buffer_duration: float = 10.0,
        device_index: Optional[int] = None
    ):
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_duration = chunk_duration
        self.chunk_size = int(sample_rate * chunk_duration)
        self.buffer_duration = buffer_duration
        self.device_index = device_index
        
        # 环形缓冲区（保存最近10秒）
        max_chunks = int(buffer_duration / chunk_duration)
        self.buffer = deque(maxlen=max_chunks)
        self.buffer_lock = threading.Lock()
        
        # 回调函数列表
        self.callbacks = []
        
        # 线程控制
        self.running = False
        self.thread = None
        
        # PyAudio 实例
        self.audio = None
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
            # 初始化 PyAudio
            import pyaudio
            self.audio = pyaudio.PyAudio()
            
            # 获取设备信息
            if self.device_index is None:
                self.device_index = self._find_usb_audio_device()
            
            device_info = self.audio.get_device_info_by_index(self.device_index)
            logger.info(f"使用音频设备: {device_info['name']}")
            
            # 打开音频流
            self.stream = self.audio.open(
                format=pyaudio.paFloat32,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                input_device_index=self.device_index,
                frames_per_buffer=self.chunk_size,
                stream_callback=self._audio_callback
            )
            
            # 启动线程
            self.running = True
            self.thread = threading.Thread(target=self._run, daemon=True, name="AudioCapture")
            self.thread.start()
            
            self.stream.start_stream()
            logger.info("✅ 音频采集线程已启动")
            return True
            
        except ImportError:
            logger.error("PyAudio 未安装，无法启动音频采集")
            return False
        except Exception as e:
            logger.error(f"启动音频采集失败: {e}", exc_info=True)
            return False
    
    def _find_usb_audio_device(self) -> int:
        """查找 WM8960 音频设备（优先使用 plughw 支持多路访问）"""
        try:
            import pyaudio
            
            # 优先查找 plughw 设备（支持软件混音，允许多路并发访问）
            for i in range(self.audio.get_device_count()):
                info = self.audio.get_device_info_by_index(i)
                name = info['name'].lower()
                if 'plughw' in name and ('wm8960' in name or '1,0' in name):
                    logger.info(f"找到 WM8960 plughw 设备 [{i}]: {info['name']} (支持多路访问)")
                    return i
            
            # 其次查找 WM8960 设备
            for i in range(self.audio.get_device_count()):
                info = self.audio.get_device_info_by_index(i)
                name = info['name'].lower()
                if 'wm8960' in name or 'usb audio' in name:
                    logger.info(f"找到 USB 音频设备 [{i}]: {info['name']}")
                    logger.warning("⚠️ 建议配置 ALSA 使用 plughw 以避免与 Stream 进程冲突")
                    return i
            
            # 未找到特定设备，使用默认输入设备
            default_device = self.audio.get_default_input_device_info()
            logger.warning(f"未找到 WM8960，使用默认设备: {default_device['name']}")
            return default_device['index']
            
        except Exception as e:
            logger.warning(f"查找音频设备失败: {e}，使用设备索引 0")
            return 0
    
    def _audio_callback(self, in_data, frame_count, time_info, status):
        """PyAudio 回调函数"""
        import pyaudio
        if status:
            logger.warning(f"音频流状态: {status}")
        
        # 转换为 NumPy 数组
        # audio_chunk: 1D NumPy array, dtype=float32, 长度为 chunk_size
        # 数值范围约为 [-1.0, 1.0]，每个元素为单声道采样点（float32 PCM）
        audio_chunk = np.frombuffer(in_data, dtype=np.float32)
        
        # 保存到环形缓冲区
        with self.buffer_lock:
            self.buffer.append((time.time(), audio_chunk))
        
        # 触发回调
        for callback in self.callbacks:
            try:
                callback(audio_chunk)
            except Exception as e:
                logger.error(f"回调函数异常: {e}")
        
        return (None, pyaudio.paContinue)
    
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
                self.stream.stop_stream()
                self.stream.close()
            except:
                pass
        
        if self.audio:
            try:
                self.audio.terminate()
            except:
                pass
        
        logger.info("✅ 音频采集已停止")
    
    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self.running and (self.thread is not None) and self.thread.is_alive()
