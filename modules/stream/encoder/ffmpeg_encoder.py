"""
FFmpeg 编码器实现
使用 FFmpeg 进行 H.264 软件编码和推流
"""

import subprocess
import threading
import time
from typing import Optional
import numpy as np
from utils.logger import setup_logger

from .base import EncoderBase

logger = setup_logger('ffmpeg_encoder')


class FFmpegEncoder(EncoderBase):
    """
    FFmpeg H.264 编码器
    
    支持 RTSP 和 RTMP 推流
    """
    
    def __init__(self, width: int, height: int, fps: int, bitrate: str):
        super().__init__(width, height, fps, bitrate)
        self.process = None
        self.stderr_thread = None
        self.stream_url = None
    
    def initialize(self, stream_url: str) -> bool:
        """初始化 FFmpeg 编码器"""
        if self._is_initialized:
            logger.warning("FFmpeg 编码器已初始化")
            return True
        
        self.stream_url = stream_url
        
        try:
            # 判断推流协议
            is_rtsp = stream_url.startswith('rtsp://')
            
            # 构建 FFmpeg 命令
            cmd = [
                'ffmpeg',
                '-y',  # 覆盖输出
                # 输入配置
                '-f', 'rawvideo',
                '-pixel_format', 'bgr24',
                '-video_size', f'{self.width}x{self.height}',
                '-framerate', str(self.fps),
                '-i', 'pipe:0',  # 从 stdin 读取
                # 编码配置
                '-c:v', 'libx264',
                '-preset', 'ultrafast',      # 最快预设
                '-tune', 'zerolatency',      # 零延迟优化
                '-b:v', self.bitrate,        # 码率
                '-maxrate', self.bitrate,    # 最大码率
                '-bufsize', f'{int(self.bitrate[:-1]) * 2}k',  # 缓冲区
                '-g', str(self.fps * 2),     # GOP 大小
                '-keyint_min', str(self.fps),
                '-pix_fmt', 'yuv420p',
                '-profile:v', 'baseline',    # H.264 Baseline
                '-an',  # 无音频
            ]
            
            # 输出配置
            if is_rtsp:
                cmd.extend([
                    '-f', 'rtsp',
                    '-rtsp_transport', 'tcp',
                    stream_url
                ])
            else:
                # RTMP/FLV
                cmd.extend([
                    '-f', 'flv',
                    stream_url
                ])
            
            logger.info(f"启动 FFmpeg 编码器")
            logger.info(f"  输入: {self.width}x{self.height} @ {self.fps}fps BGR24")
            logger.info(f"  输出: H.264 @ {self.bitrate}")
            logger.info(f"  推流: {stream_url}")
            
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
            
            if self.process.poll() is not None:
                raise RuntimeError(
                    f"FFmpeg 进程启动后立即退出，返回码: {self.process.returncode}"
                )
            
            self._is_initialized = True
            logger.info("✅ FFmpeg 编码器已启动")
            return True
            
        except Exception as e:
            logger.error(f"FFmpeg 编码器初始化失败: {e}")
            self._cleanup_process()
            return False
    
    def encode(self, frame: np.ndarray) -> bool:
        """编码一帧"""
        if not self._is_initialized or not self.process:
            return False
        
        try:
            self.process.stdin.write(frame.tobytes())
            self.process.stdin.flush()
            return True
            
        except BrokenPipeError:
            logger.error("FFmpeg 管道断开")
            self._is_initialized = False
            return False
        except IOError as e:
            logger.error(f"写入 FFmpeg 失败: {e}")
            return False
    
    def release(self):
        """释放编码器资源"""
        logger.info("正在释放 FFmpeg 编码器...")
        self._cleanup_process()
        self._is_initialized = False
        logger.info("✅ FFmpeg 编码器已释放")
    
    def is_alive(self) -> bool:
        """检查 FFmpeg 进程是否存活"""
        if not self.process:
            return False
        return self.process.poll() is None
    
    def _start_stderr_reader(self):
        """启动 stderr 读取线程（避免管道阻塞）"""
        def read_stderr():
            try:
                for line in self.process.stderr:
                    line_str = line.decode('utf-8', errors='ignore').strip()
                    if line_str:
                        # 只记录错误和警告
                        if 'error' in line_str.lower() or 'warning' in line_str.lower():
                            logger.warning(f"FFmpeg: {line_str}")
            except:
                pass
        
        self.stderr_thread = threading.Thread(target=read_stderr, daemon=True)
        self.stderr_thread.start()
    
    def _cleanup_process(self):
        """清理 FFmpeg 进程"""
        if self.process:
            try:
                self.process.stdin.close()
                self.process.wait(timeout=5)
                logger.info("FFmpeg 进程正常退出")
            except subprocess.TimeoutExpired:
                logger.warning("FFmpeg 进程未响应，强制终止")
                self.process.kill()
                self.process.wait()
            except Exception as e:
                logger.error(f"清理 FFmpeg 进程失败: {e}")
                try:
                    self.process.kill()
                except:
                    pass
            finally:
                self.process = None
