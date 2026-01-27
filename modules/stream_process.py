"""
流媒体管理进程
负责按需推流到 ZLMediaKit
"""

import time
import subprocess
from utils.logger import setup_logger
from utils.ipc import IPCHelper

logger = setup_logger('stream_manager')


class StreamManagerProcess:
    """
    流媒体管理进程 - 负责按需推流到 ZLMediaKit
    
    功能：
    1. 接收平台推流指令
    2. 启动 FFmpeg 推流进程
    3. 管理推流生命周期
    4. 停止推流
    """
    
    def __init__(self, ipc_queue, shared_state, config):
        self.ipc = IPCHelper(ipc_queue, 'stream_manager')
        self.state = shared_state
        self.config = config
        self.running = True
        
        # 推流配置
        self.zlm_server = config['stream']['zlm_server']
        self.stream_key = config['stream']['stream_key'].format(
            device_id=config['device']['id']
        )
        
        # FFmpeg 进程
        self.ffmpeg_process = None
        
        logger.info(f"流媒体管理进程初始化完成")
        logger.info(f"  推流地址: {self.zlm_server}/{self.stream_key}")
    
    def run(self):
        """主循环"""
        logger.info("📹 流媒体管理进程启动")
        
        last_heartbeat = time.time()
        
        try:
            while self.running:
                # 处理消息
                msg = self.ipc.receive(timeout=1.0)
                if msg:
                    msg_type = msg.get('type')
                    
                    if msg_type == 'start_stream':
                        logger.info("📤 收到开始推流指令")
                        self._start_stream()
                    
                    elif msg_type == 'stop_stream':
                        logger.info("⏹️  收到停止推流指令")
                        self._stop_stream()
                    
                    elif msg_type == 'shutdown':
                        logger.info("收到关闭信号")
                        break
                
                # 定期发送心跳
                if time.time() - last_heartbeat > 10:
                    self.ipc.send_heartbeat()
                    last_heartbeat = time.time()
                
        except KeyboardInterrupt:
            logger.info("检测到中断信号")
        finally:
            self._stop_stream()
            logger.info("流媒体管理进程退出")
    
    def _start_stream(self):
        """启动推流"""
        # 如果已经在推流，先停止
        if self.ffmpeg_process:
            logger.warning("已有推流进程在运行，先停止")
            self._stop_stream()
        
        try:
            # 构建 FFmpeg 命令
            stream_url = f"{self.zlm_server}/{self.stream_key}"
            
            # 初版使用测试源
            cmd = [
                'ffmpeg',
                '-f', 'lavfi',
                '-i', 'testsrc=size=1280x720:rate=25',
                '-f', 'lavfi',
                '-i', 'sine=frequency=1000:sample_rate=16000',
                '-c:v', 'libx264',
                '-preset', 'ultrafast',
                '-b:v', self.config['stream']['bitrate'],
                '-c:a', 'aac',
                '-f', 'flv',
                stream_url
            ]
            
            # 真实推流命令（树莓派摄像头）
            # cmd = [
            #     'ffmpeg',
            #     '-f', 'v4l2',
            #     '-i', '/dev/video0',
            #     '-c:v', 'h264_v4l2m2m',  # 硬件编码
            #     '-b:v', self.config['stream']['bitrate'],
            #     '-f', 'flv',
            #     stream_url
            # ]
            
            logger.info(f"启动 FFmpeg 推流: {' '.join(cmd)}")
            
            # 启动进程
            self.ffmpeg_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # 更新状态
            self.state['is_streaming'] = True
            logger.info("✅ 推流已启动")
            
        except Exception as e:
            logger.error(f"启动推流失败: {e}")
            self.ffmpeg_process = None
    
    def _stop_stream(self):
        """停止推流"""
        if not self.ffmpeg_process:
            return
        
        try:
            logger.info("停止 FFmpeg 推流进程")
            self.ffmpeg_process.terminate()
            self.ffmpeg_process.wait(timeout=5)
            logger.info("✅ 推流已停止")
            
        except subprocess.TimeoutExpired:
            logger.warning("FFmpeg 进程未响应，强制杀死")
            self.ffmpeg_process.kill()
            
        finally:
            self.ffmpeg_process = None
            self.state['is_streaming'] = False
