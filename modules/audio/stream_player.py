"""
Opus 实时音频播放器
负责解码 Opus 二进制数据并播放
"""

from queue import Queue, Empty
from typing import Optional
import threading
import numpy as np
import sounddevice as sd
import opuslib
from utils.logger import setup_logger

logger = setup_logger('stream_player')


class StreamAudioPlayer:
    """
    Opus 实时音频播放器

    仅负责解码和播放，不管理网络连接。
    """

    def __init__(self, sample_rate: int = 16000, channels: int = 1, max_frame_size: int = 960):
        self.sample_rate = sample_rate
        self.channels = channels
        self.max_frame_size = max_frame_size

        self._decoder = opuslib.Decoder(sample_rate, channels)
        self._queue: Queue = Queue(maxsize=50)
        self._stream: Optional[sd.OutputStream] = None
        self._running = False
        self._lock = threading.Lock()

    def start(self) -> bool:
        with self._lock:
            if self._running:
                return True
            try:
                self._stream = sd.OutputStream(
                    samplerate=self.sample_rate,
                    channels=self.channels,
                    dtype='float32',
                    callback=self._audio_callback
                )
                self._stream.start()
                self._running = True
                logger.info("✅ 远程喊话播放已启动")
                return True
            except Exception as exc:
                logger.error(f"启动播放失败: {exc}")
                self._running = False
                return False

    def stop(self) -> None:
        with self._lock:
            if not self._running:
                return
            self._running = False
            if self._stream:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception as exc:
                    logger.error(f"停止播放失败: {exc}")
            self._stream = None
            self._clear_queue()
            logger.info("✅ 远程喊话播放已停止")

    def enqueue_opus(self, packet: bytes) -> None:
        if not packet:
            return
        try:
            pcm_bytes = self._decoder.decode(packet, self.max_frame_size)
            pcm = np.frombuffer(pcm_bytes, dtype=np.int16)
            audio = pcm.astype(np.float32) / 32768.0
            self._queue.put_nowait(audio)
        except Exception as exc:
            logger.error(f"Opus 解码失败: {exc}")

    def _audio_callback(self, outdata, frames, time_info, status):
        if status:
            logger.warning(f"播放状态: {status}")

        outdata[:] = 0.0
        try:
            audio = self._queue.get_nowait()
        except Empty:
            return

        if audio.ndim == 1 and self.channels == 1:
            audio = audio.reshape(-1, 1)

        length = min(len(audio), frames)
        outdata[:length] = audio[:length]

    def _clear_queue(self) -> None:
        try:
            while True:
                self._queue.get_nowait()
        except Empty:
            return
