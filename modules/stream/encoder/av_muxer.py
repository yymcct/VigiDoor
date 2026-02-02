"""
音视频混流器（RTSP 版本）
将视频流和音频流合并推送到 RTSP 服务器
"""

import subprocess
import threading
import time
from typing import Optional
import numpy as np
from utils.logger import setup_logger

from .base import EncoderBase

logger = setup_logger('av_muxer')


class AVMuxer(EncoderBase):
    """
    音视频混流器（RTSP）
    
    架构：
    - 视频输入：通过 stdin 接收 RGB24 原始帧
    - 音频输入：FFmpeg 直接从 ALSA 设备采集
    - 输出：RTSP 流（H.264 + AAC）
    
    FFmpeg 命令示例：
    ffmpeg -f rawvideo -pix_fmt rgb24 -s 1920x1080 -r 25 -i pipe:0 \
           -f alsa -i hw:1,0 -ac 1 \
           -c:v libx264 -preset ultrafast -tune zerolatency \
           -c:a aac -b:a 128k -ar 16000 \
           -f rtsp -rtsp_transport tcp \
           rtsp://server/live/camera001
    """
    
    def __init__(
        self,
        width: int,
        height: int,
        fps: int,
        video_bitrate: str,
        audio_device: str = "plughw:1,0",
        audio_bitrate: str = "128k",
        audio_sample_rate: int = 16000,
        audio_channels: int = 1
    ):
        """
        初始化音视频混流器
        
        Args:
            width: 视频宽度
            height: 视频高度
            fps: 帧率
            video_bitrate: 视频码率（例如："2000k"）
            audio_device: ALSA 音频设备（例如："plughw:1,0"，使用 plughw 支持多路访问）
            audio_bitrate: 音频码率（例如："128k"）
            audio_sample_rate: 音频采样率（Hz）
            audio_channels: 音频通道数
        """
        super().__init__(width, height, fps, video_bitrate)
        self.video_bitrate = video_bitrate
        self.audio_device = audio_device
        self.audio_bitrate = audio_bitrate
        self.audio_sample_rate = audio_sample_rate
        self.audio_channels = audio_channels
        
        # FFmpeg 进程
        self.process = None
        self.stderr_thread = None
        self.stream_url = None
        
        # 状态
        self._is_initialized = False
        
        logger.info(f"音视频混流器初始化")
        logger.info(f"  视频: {width}x{height} @ {fps}fps, {video_bitrate}")
        logger.info(f"  音频: {audio_device}, {audio_sample_rate}Hz, {audio_bitrate}")
    
    def initialize(self, stream_url: str) -> bool:
        """
        初始化混流器并启动 FFmpeg（音频默认启用）
        
        Args:
            stream_url: RTSP 推流地址
            
        Returns:
            是否初始化成功
        """
        if self._is_initialized:
            logger.warning("混流器已初始化")
            return True
        
        self.stream_url = stream_url
        
        try:
            # 构建 FFmpeg 命令（音频始终启用）
            cmd = self._build_ffmpeg_command()
            
            logger.info(f"启动 FFmpeg 混流器（音视频混流）")
            logger.info(f"  推流地址: {stream_url}")
            logger.debug(f"  FFmpeg 命令: {' '.join(cmd)}")
            
            # 启动 FFmpeg 子进程
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=10**8  # 100MB 缓冲区
            )
            
            # 启动 stderr 读取线程
            self._start_stderr_reader()
            
            # 等待启动
            time.sleep(0.5)
            
            # 检查进程是否存活
            if self.process.poll() is not None:
                logger.error("FFmpeg 进程启动后立即退出")
                return False
            
            self._is_initialized = True
            logger.info("✅ 混流器初始化完成")
            return True
            
        except Exception as e:
            logger.error(f"混流器初始化失败: {e}", exc_info=True)
            return False
    
    def _build_ffmpeg_command(self) -> list:
        """构建 FFmpeg 命令（音频始终启用）"""
        cmd = [
            'ffmpeg',
            '-y',  # 覆盖输出
            '-loglevel', 'warning',  # 减少日志输出
        ]
        
        # === 视频输入配置 ===
        cmd.extend([
            '-f', 'rawvideo',
            '-pixel_format', 'rgb24',
            '-video_size', f'{self.width}x{self.height}',
            '-framerate', str(self.fps),
            '-i', 'pipe:0',  # 从 stdin 读取视频
        ])
        
        # === 音频输入配置（始终启用）===
        cmd.extend([
            '-f', 'alsa',
            '-ac', str(self.audio_channels),  # 通道数
            '-ar', str(self.audio_sample_rate),  # 采样率
            '-i', self.audio_device,  # ALSA 设备
        ])
        
        # === 视频编码配置 ===
        cmd.extend([
            '-c:v', 'libx264',
            '-preset', 'ultrafast',      # 最快预设
            '-tune', 'zerolatency',      # 零延迟优化
            '-b:v', self.video_bitrate,  # 视频码率
            '-maxrate', self.video_bitrate,
            '-bufsize', f'{int(self.video_bitrate[:-1]) * 2}k',
            '-g', str(self.fps * 2),     # GOP 大小
            '-keyint_min', str(self.fps),
            '-pix_fmt', 'yuv420p',
            '-profile:v', 'baseline',    # H.264 Baseline
        ])
        
        # === 音频编码配置（AAC）===
        cmd.extend([
            '-c:a', 'aac',
            '-b:a', self.audio_bitrate,
            '-ar', str(self.audio_sample_rate),  # 采样率
        ])
        
        # === RTSP 输出配置 ===
        cmd.extend([
            '-f', 'rtsp',
            '-rtsp_transport', 'tcp',
            self.stream_url
        ])
        
        return cmd
    
    def _start_stderr_reader(self):
        """启动 stderr 读取线程"""
        def read_stderr():
            while self.process:
                try:
                    line = self.process.stderr.readline()
                    if not line:
                        break
                    
                    line = line.decode('utf-8', errors='ignore').strip()
                    if line:
                        # 过滤掉不重要的日志
                        if 'frame=' in line or 'time=' in line:
                            logger.debug(f"FFmpeg: {line}")
                        elif 'error' in line.lower() or 'warning' in line.lower():
                            logger.warning(f"FFmpeg: {line}")
                        
                except Exception as e:
                    logger.debug(f"读取 stderr 异常: {e}")
                    break
        
        self.stderr_thread = threading.Thread(target=read_stderr, daemon=True, name="FFmpeg-stderr")
        self.stderr_thread.start()
    
    def encode(self, frame: np.ndarray) -> bool:
        """
        编码并发送一帧（仅视频，音频由 FFmpeg 自己采集）
        
        Args:
            frame: RGB24 格式的帧 (H, W, 3)
            
        Returns:
            是否成功
        """
        if not self._is_initialized or not self.process:
            logger.error("混流器未初始化")
            return False
        
        try:
            # 写入 stdin
            self.process.stdin.write(frame.tobytes())
            return True
            
        except BrokenPipeError:
            logger.error("FFmpeg 管道已断开")
            return False
        except Exception as e:
            logger.error(f"写入帧失败: {e}")
            return False
    
    def release(self):
        """释放混流器"""
        if not self._is_initialized:
            return
        
        logger.info("正在释放混流器...")
        
        try:
            # 关闭 stdin
            if self.process and self.process.stdin:
                self.process.stdin.close()
            
            # 等待进程结束
            if self.process:
                self.process.wait(timeout=5)
                logger.info(f"FFmpeg 进程已退出，返回码: {self.process.returncode}")
        except subprocess.TimeoutExpired:
            logger.warning("FFmpeg 进程未响应，强制终止")
            self.process.kill()
        except Exception as e:
            logger.error(f"释放混流器失败: {e}")
        
        self.process = None
        self._is_initialized = False
        logger.info("✅ 混流器已释放")
    
    def is_alive(self) -> bool:
        """检查 FFmpeg 进程是否存活"""
        return self.process is not None and self.process.poll() is None
