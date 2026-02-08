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
        self.last_error = None  # 记录最后的错误信息
        self.error_type = None  # 错误类型
    
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
                    '-timeout', '5000000',  # 5秒超时 (微秒)
                    stream_url
                ])
            else:
                # RTMP/FLV
                cmd.extend([
                    '-f', 'flv',
                    '-timeout', '5000000',  # 5秒超时
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
        
        # 检查 FFmpeg 进程是否还活着
        if self.process.poll() is not None:
            exit_code = self.process.returncode
            logger.error(f"❌ FFmpeg 进程已退出，返回码: {exit_code}")
            self._diagnose_error()
            self._is_initialized = False
            return False
        
        try:
            self.process.stdin.write(frame.tobytes())
            self.process.stdin.flush()
            return True
            
        except BrokenPipeError:
            exit_code = self.process.poll()
            logger.error(f"❌ FFmpeg 管道断开（Broken Pipe），进程退出码: {exit_code}")
            self._diagnose_error()
            self._is_initialized = False
            return False
        except IOError as e:
            logger.error(f"❌ 写入 FFmpeg 失败: {e}")
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
                        # 记录所有FFmpeg输出以便诊断
                        if 'error' in line_str.lower():
                            logger.error(f"FFmpeg: {line_str}")
                            self.last_error = line_str  # 保存错误信息
                            self._classify_error(line_str)
                        elif 'warning' in line_str.lower():
                            logger.warning(f"FFmpeg: {line_str}")
                        else:
                            # 记录重要的状态信息
                            if any(keyword in line_str.lower() for keyword in 
                                   ['connection', 'timeout', 'refused', 'failed', 'unable', 'broken pipe']):
                                logger.warning(f"FFmpeg: {line_str}")
                                self.last_error = line_str
                                self._classify_error(line_str)
                            else:
                                logger.debug(f"FFmpeg: {line_str}")
            except Exception as e:
                logger.error(f"stderr读取线程异常: {e}")
        
        self.stderr_thread = threading.Thread(target=read_stderr, daemon=True)
        self.stderr_thread.start()
    
    def _classify_error(self, error_msg: str):
        """分类错误信息"""
        error_msg_lower = error_msg.lower()
        if 'broken pipe' in error_msg_lower:
            self.error_type = 'BROKEN_PIPE'
        elif 'connection refused' in error_msg_lower:
            self.error_type = 'CONNECTION_REFUSED'
        elif 'timeout' in error_msg_lower:
            self.error_type = 'TIMEOUT'
        elif 'no route to host' in error_msg_lower:
            self.error_type = 'NETWORK_ERROR'
        else:
            self.error_type = 'UNKNOWN'
    
    def _diagnose_error(self):
        """诊断并输出错误建议"""
        logger.error("="*60)
        logger.error("📋 推流失败诊断")
        logger.error(f"   推流地址: {self.stream_url}")
        
        if self.last_error:
            logger.error(f"   错误信息: {self.last_error}")
        
        if self.error_type == 'BROKEN_PIPE':
            logger.error("   错误类型: 管道断开 (Broken Pipe)")
            logger.error("")
            logger.error("🔧 可能原因和解决方案：")
            logger.error("   1. RTSP/RTMP 服务器断开连接")
            logger.error("      → 检查 ZLMediaKit 是否正在运行")
            logger.error("      → 测试命令: curl -v http://192.168.1.119:80/index/api/getMediaList")
            logger.error("   2. 服务器超时配置")
            logger.error("      → 检查 ZLMediaKit 的超时配置")
            logger.error("   3. 网络连接不稳定")
            logger.error("      → 测试命令: ping 192.168.1.119")
            logger.error("      → 检查防火墙设置")
        elif self.error_type == 'CONNECTION_REFUSED':
            logger.error("   错误类型: 连接被拒绝")
            logger.error("")
            logger.error("🔧 解决方案：")
            logger.error("   1. 检查 RTSP 服务器是否启动")
            logger.error("   2. 验证端口是否正确（默认 RTSP: 554 或 8554）")
            logger.error("   3. 检查防火墙是否阻止连接")
        elif self.error_type == 'TIMEOUT':
            logger.error("   错误类型: 连接超时")
            logger.error("")
            logger.error("🔧 解决方案：")
            logger.error("   1. 检查网络连接")
            logger.error("   2. 增加 FFmpeg 超时设置")
            logger.error("   3. 验证服务器地址是否正确")
        else:
            logger.error("   错误类型: 未知错误")
            logger.error("")
            logger.error("🔧 建议：")
            logger.error("   1. 检查 FFmpeg 日志获取详细信息")
            logger.error("   2. 验证推流地址格式是否正确")
            logger.error("   3. 测试服务器是否可访问")
        
        logger.error("="*60)
    
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
