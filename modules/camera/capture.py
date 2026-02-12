"""
采集循环管理器
负责协调驱动、共享内存、通信和监控
"""

import time
from utils.logger import setup_logger
from utils.frame_buffer import SharedFrameBuffer
from .base import CameraDriverBase
from .communicator import CameraCommunicator
from .monitor import PerformanceMonitor

logger = setup_logger('camera_capture')


class CaptureManager:
    """
    采集管理器
    
    职责：
    - 协调摄像头驱动
    - 管理帧捕获循环
    - 写入共享内存
    - 帧率控制
    """
    
    def __init__(
        self,
        driver: CameraDriverBase,
        frame_buffer: SharedFrameBuffer,
        communicator: CameraCommunicator,
        monitor: PerformanceMonitor,
        target_fps: int
    ):
        """
        初始化采集管理器
        
        Args:
            driver: 摄像头驱动实例
            frame_buffer: 共享内存帧缓冲
            communicator: 通信器
            monitor: 性能监控器
            target_fps: 目标帧率
        """
        self.driver = driver
        self.frame_buffer = frame_buffer
        self.communicator = communicator
        self.monitor = monitor
        self.target_fps = target_fps
        self.running = True
        
        self.frame_interval = 1.0 / target_fps
        
        logger.info(f"采集管理器初始化完成")
        logger.info(f"  目标帧率: {target_fps} FPS")
        logger.info(f"  帧间隔: {self.frame_interval*1000:.2f} ms")
    
    def run(self):
        """
        主采集循环
        """
        logger.info("🎥 开始采集循环")
        driver_info = self.driver.get_info()
        logger.info(f"  使用驱动: {driver_info.get('driver_type', 'unknown')}")
        
        while self.running:
            loop_start = time.time()
            
            try:
                # 1. 捕获帧
                frame = self.driver.capture_frame()
                if frame is None:
                    logger.error("捕获帧失败")
                    time.sleep(0.1)
                    continue
                
                # 2. 写入共享内存
                timestamp = time.time()
                frame_id = self.monitor.frame_count
                
                self.frame_buffer.write_frame(
                    frame=frame,
                    frame_id=frame_id,
                    timestamp=timestamp
                )
                
                # 3. 通知其他进程（已优化：OSD渲染器直接轮询共享内存，无需事件通知）
                # self.communicator.notify_frame_ready(frame_id, timestamp)
                
                # 4. 更新性能统计
                self.monitor.on_frame_captured()
                
                if self.monitor.update():
                    stats = self.monitor.get_stats()
                    # logger.debug(
                    #     f"采集统计: {stats['current_fps']} FPS, "
                    #     f"总帧数: {stats['frame_count']}"
                    # )
                
                # 5. 发送心跳
                stats = self.monitor.get_stats()
                self.communicator.send_heartbeat(
                    fps=stats['current_fps'],
                    frame_count=stats['frame_count']
                )
                
                # 6. 检查关闭信号
                if self.communicator.check_shutdown_signal():
                    logger.info("收到关闭信号，退出采集循环")
                    break
                
                # 7. 帧率控制
                elapsed = time.time() - loop_start
                if elapsed < self.frame_interval:
                    time.sleep(self.frame_interval - elapsed)
                
            except KeyboardInterrupt:
                logger.info("检测到中断信号")
                break
            except Exception as e:
                logger.error(f"采集循环异常: {e}", exc_info=True)
                time.sleep(0.1)
        
        logger.info("采集循环已退出")
    
    def stop(self):
        logger.info("正在停止采集...")
        self.running = False
