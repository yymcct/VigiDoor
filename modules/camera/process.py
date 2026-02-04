"""
摄像头采集进程
"""

import os
import platform

from core.ipc import IPCClient
from modules.camera.base import CameraDriverBase
from utils.logger import setup_logger
from utils.frame_buffer import SharedFrameBuffer
from utils.system import is_raspberry_pi

from .drivers import Picamera2Driver, OpenCVDriver
from .communicator import CameraCommunicator
from .monitor import PerformanceMonitor
from .capture import CaptureManager

logger = setup_logger('camera_process')


class CameraProcess:
    """
    视频采集进程 - 负责持续采集原始 RGB 帧
    
    功能：
    1. 自动选择合适的摄像头驱动（Picamera2 > OpenCV > Simulator）
    2. 将帧写入共享内存
    3. 发送"新帧就绪"消息到消息队列
    4. 监控采集帧率，异常时上报 Supervisor
    
    架构：
    - 驱动层：抽象的摄像头驱动接口，支持多种硬件
    - 采集层：CaptureManager 管理采集循环
    - 通信层：CameraCommunicator 封装 IPC 通信
    - 监控层：PerformanceMonitor 统计性能指标
    """
    
    def __init__(self, ipc_client: IPCClient, shared_state, config):
        """
        初始化摄像头进程
        
        Args:
            ipc_client: IPC 客户端
            shared_state: 共享状态（预留）
            config: 配置字典
        """
        self.ipc = ipc_client
        self.state = shared_state
        self.config = config
        self.running = True
        
        # 从配置读取参数
        self.width = config['camera']['width']
        self.height = config['camera']['height']
        self.target_fps = config['camera']['target_fps']
        self.format = config['camera']['format']
        self.shared_memory_name = config['camera']['shared_memory_name']
        
        # 组件（延迟初始化）
        self.frame_buffer = None
        self.driver = None
        self.communicator = None
        self.monitor = None
        self.capture_manager = None
        
        logger.info(f"📹 视频采集进程初始化")
        logger.info(f"   分辨率: {self.width}x{self.height}")
        logger.info(f"   目标帧率: {self.target_fps} FPS")
        logger.info(f"   像素格式: {self.format}")
    
    def run(self):
        logger.info("🚀 视频采集进程启动")
        
        try:            
            self._init_shared_memory()
                        
            self.driver = self._init_driver()
            
            if not self.driver or not self.driver.is_initialized():
                logger.error("❌ 无可用的摄像头驱动")
                return
            
            self._init_components()
            
            self.capture_manager.run()
            
        except KeyboardInterrupt:
            logger.info("检测到中断信号")
        except Exception as e:
            logger.error(f"进程异常: {e}", exc_info=True)
        finally:
            self._cleanup()
            logger.info("视频采集进程退出")
    
    def _init_shared_memory(self):
        """初始化共享内存帧缓冲"""
        try:
            self.frame_buffer = SharedFrameBuffer(
                width=self.width,
                height=self.height,
                name=self.shared_memory_name,
                create=True
            )
            logger.info("✅ 共享内存帧缓冲初始化成功")
            
        except Exception as e:
            logger.error(f"❌ 共享内存初始化失败: {e}")
            raise
    
    def _init_driver(self) -> CameraDriverBase:
        """根据系统类型自动选择驱动"""
        is_rpi = is_raspberry_pi()
        
        if is_rpi:
            name, DriverClass = 'Picamera2', Picamera2Driver
            logger.info("检测到树莓派系统，使用 Picamera2 驱动")
        else:
            name, DriverClass = 'OpenCV', OpenCVDriver
            logger.info("检测到 Ubuntu/通用系统，使用 OpenCV 驱动")
        
        try:
            logger.info(f"初始化 {name} 驱动...")
            driver = DriverClass(
                width=self.width,
                height=self.height,
                target_fps=self.target_fps,
                format=self.format
            )
            
            if driver.initialize():
                logger.info(f"✅ {name} 驱动初始化成功")
                return driver
            else:
                logger.error(f"❌ {name} 驱动初始化失败")
                return None
                
        except Exception as e:
            logger.error(f"❌ {name} 驱动初始化异常: {e}")
            return None
    
    def _init_components(self):
        """初始化各个功能组件"""
        self.communicator = CameraCommunicator(
            ipc_client=self.ipc,
            width=self.width,
            height=self.height
        )
        logger.info("✅ 通信器初始化完成")
        
        self.monitor = PerformanceMonitor(
            target_fps=self.target_fps,
            low_fps_threshold=0.8
        )
        logger.info("✅ 性能监控器初始化完成")
        
        self.capture_manager = CaptureManager(
            driver=self.driver,
            frame_buffer=self.frame_buffer,
            communicator=self.communicator,
            monitor=self.monitor,
            target_fps=self.target_fps
        )
        logger.info("✅ 采集管理器初始化完成")
    
    def _cleanup(self):
        """清理资源"""
        logger.info("正在清理资源...")
        
        if self.driver:
            try:
                self.driver.release()
            except Exception as e:
                logger.error(f"释放驱动资源失败: {e}")
        
        if self.frame_buffer:
            try:
                self.frame_buffer.cleanup()
                logger.info("已清理共享内存")
            except Exception as e:
                logger.error(f"清理共享内存失败: {e}")
        
        logger.info("✅ 资源清理完成")
