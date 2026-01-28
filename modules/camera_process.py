"""
视频采集进程
负责持续采集原始RGB帧并写入共享内存
"""

import time
import numpy as np
import cv2
from utils.logger import setup_logger
from core.ipc import IPCClient, MessageType
from core.ipc.message import FrameReadyMessage
from core.ipc.registry import ProcessName
from utils.frame_buffer import SharedFrameBuffer

logger = setup_logger('camera_process')


class CameraProcess:
    """
    视频采集进程 - 负责持续采集原始RGB帧
    
    功能：
    1. 使用picamera2持续采集原始RGB帧
    2. 将帧写入共享内存
    3. 发送"新帧就绪"消息到消息队列
    4. 监控采集帧率，异常时上报Supervisor
    """
    
    def __init__(self, ipc_client: IPCClient, shared_state, config):
        self.ipc = ipc_client
        self.state = shared_state
        self.config = config
        self.running = True
        
        # 视频配置
        self.width = config['camera']['width']
        self.height = config['camera']['height']
        self.target_fps = config['camera']['target_fps']
        self.format = config['camera']['format']
        
        # 共享内存帧缓冲
        self.frame_buffer = None
        
        # 统计信息
        self.frame_count = 0
        self.last_fps_check = time.time()
        self.fps_counter = 0
        self.current_fps = 0
        
        logger.info(f"视频采集进程初始化")
        logger.info(f"  分辨率: {self.width}x{self.height}")
        logger.info(f"  目标帧率: {self.target_fps} FPS")
        logger.info(f"  像素格式: {self.format}")
    
    def run(self):
        """主循环"""
        logger.info("📹 视频采集进程启动")
        
        try:
            # 初始化共享内存
            self._init_shared_memory()
            
            # 初始化摄像头
            camera = self._init_camera()
            
            if not camera:
                logger.error("摄像头初始化失败，进入模拟模式")
                self._run_simulation_mode()
                return
            
            # 主采集循环
            self._capture_loop(camera)
            
        except KeyboardInterrupt:
            logger.info("检测到中断信号")
        except Exception as e:
            logger.error(f"采集循环异常: {e}", exc_info=True)
        finally:
            self._cleanup()
            logger.info("视频采集进程退出")
    
    def _init_shared_memory(self):
        """初始化共享内存帧缓冲"""
        try:
            self.frame_buffer = SharedFrameBuffer(
                width=self.width,
                height=self.height,
                name=self.config['camera']['shared_memory_name'],
                create=True 
            )
            logger.info("✅ 共享内存帧缓冲初始化成功")
            
        except Exception as e:
            logger.error(f"共享内存初始化失败: {e}")
            raise
    
    def _init_camera(self):
        """初始化摄像头"""
        try:
            # 尝试使用 picamera2（树莓派）
            try:
                from picamera2 import Picamera2
                
                camera = Picamera2()
                
                # 配置摄像头
                config = camera.create_preview_configuration(
                    main={
                        "size": (self.width, self.height),
                        "format": self.format
                    }
                )
                camera.configure(config)
                
                # 启动摄像头
                camera.start()
                
                # 预热（丢弃前几帧）
                logger.info("摄像头预热中...")
                for _ in range(10):
                    camera.capture_array()
                    time.sleep(0.1)
                
                logger.info("✅ Picamera2 初始化成功")
                return {'type': 'picamera2', 'camera': camera}
                
            except ImportError:
                logger.warning("Picamera2 不可用，尝试使用 OpenCV")
                
                # 尝试使用 OpenCV（通用方案）
                import cv2
                
                camera = cv2.VideoCapture(0)
                camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                camera.set(cv2.CAP_PROP_FPS, self.target_fps)
                
                if not camera.isOpened():
                    raise RuntimeError("无法打开摄像头")
                
                # 预热
                logger.info("摄像头预热中...")
                for _ in range(10):
                    camera.read()
                    time.sleep(0.1)
                
                logger.info("✅ OpenCV 摄像头初始化成功")
                return {'type': 'opencv', 'camera': camera}
                
        except Exception as e:
            logger.error(f"摄像头初始化失败: {e}")
            return None
    
    def _capture_loop(self, camera):
        """采集循环"""
        camera_type = camera['type']
        cam = camera['camera']
        
        last_heartbeat = time.time()
        frame_interval = 1.0 / self.target_fps
        
        logger.info(f"开始采集循环 (目标帧率: {self.target_fps} FPS)")
        
        while self.running:
            loop_start = time.time()
            
            try:
                # 捕获帧
                if camera_type == 'picamera2':
                    frame = cam.capture_array()
                elif camera_type == 'opencv':
                    ret, frame = cam.read()
                    if not ret:
                        logger.error("读取帧失败")
                        time.sleep(0.1)
                        continue
                    # OpenCV返回BGR，转换为RGB
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                else:
                    raise ValueError(f"未知摄像头类型: {camera_type}")
                
                # 写入共享内存
                self.frame_buffer.write_frame(
                    frame=frame,
                    frame_id=self.frame_count,
                    timestamp=time.time()
                )
                
                # 发送新帧就绪通知
                self._notify_frame_ready(self.frame_count)
                
                # 更新统计
                self.frame_count += 1
                self.fps_counter += 1
                
                # 每秒统计一次FPS
                if time.time() - self.last_fps_check >= 1.0:
                    self.current_fps = self.fps_counter
                    self.fps_counter = 0
                    self.last_fps_check = time.time()
                    
                    # 检测帧率异常
                    if self.current_fps < self.target_fps * 0.8:
                        logger.warning(
                            f"⚠️ 帧率过低: {self.current_fps} FPS "
                            f"(目标: {self.target_fps} FPS)"
                        )
                
                # 定期发送心跳
                if time.time() - last_heartbeat > 1.0:
                    self._send_heartbeat()
                    last_heartbeat = time.time()
                
                # 检查关闭信号
                msg = self.ipc.receive(timeout=0.001)
                if msg:
                    msg_dict = msg.to_dict() if hasattr(msg, 'to_dict') else msg
                    if msg_dict.get('type') in ['shutdown', MessageType.SHUTDOWN.value]:
                        logger.info("收到关闭信号")
                        break
                
                # 帧率控制
                elapsed = time.time() - loop_start
                if elapsed < frame_interval:
                    time.sleep(frame_interval - elapsed)
                
            except Exception as e:
                logger.error(f"采集帧异常: {e}", exc_info=True)
                time.sleep(0.1)
    
    def _run_simulation_mode(self):
        """模拟模式运行（无真实摄像头时）"""
        logger.info("🎬 进入模拟采集模式")
        
        try:            
            frame_interval = 1.0 / self.target_fps
            last_heartbeat = time.time()
            
            while self.running:
                loop_start = time.time()
                
                # 生成模拟帧（渐变色彩）
                frame = self._generate_test_frame(self.frame_count)
                
                # 写入共享内存
                self.frame_buffer.write_frame(
                    frame=frame,
                    frame_id=self.frame_count,
                    timestamp=time.time()
                )
                
                # 发送通知
                self._notify_frame_ready(self.frame_count)
                
                self.frame_count += 1
                self.fps_counter += 1
                
                # 统计FPS
                if time.time() - self.last_fps_check >= 1.0:
                    self.current_fps = self.fps_counter
                    logger.debug(f"模拟采集: {self.current_fps} FPS")
                    self.fps_counter = 0
                    self.last_fps_check = time.time()
                
                # 心跳
                if time.time() - last_heartbeat > 1.0:
                    self._send_heartbeat()
                    last_heartbeat = time.time()
                
                # 检查关闭信号
                msg = self.ipc.receive(timeout=0.001)
                if msg:
                    msg_dict = msg.to_dict() if hasattr(msg, 'to_dict') else msg
                    if msg_dict.get('type') in ['shutdown', MessageType.SHUTDOWN.value]:
                        break
                
                # 帧率控制
                elapsed = time.time() - loop_start
                if elapsed < frame_interval:
                    time.sleep(frame_interval - elapsed)
                    
        except Exception as e:
            logger.error(f"模拟模式异常: {e}", exc_info=True)
    
    def _generate_test_frame(self, frame_id):
        """生成测试帧（彩色渐变 + 时间戳文字）"""
        # 创建渐变背景
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        # 时间动画效果
        phase = (frame_id % 100) / 100.0
        
        # RGB渐变
        frame[:, :, 0] = int(127 + 127 * np.sin(phase * 2 * np.pi))  # R
        frame[:, :, 1] = int(127 + 127 * np.sin((phase + 0.33) * 2 * np.pi))  # G
        frame[:, :, 2] = int(127 + 127 * np.sin((phase + 0.67) * 2 * np.pi))  # B
        
        # 尝试添加文字（需要cv2）
        try:
            import cv2
            text = f"Frame: {frame_id} | FPS: {self.current_fps}"
            cv2.putText(
                frame, text, (50, 50),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2
            )
        except:
            pass
        
        return frame
    
    def _notify_frame_ready(self, frame_id):
        msg = FrameReadyMessage(
            frame_id=frame_id,
            timestamp=time.time(),
            width=self.width,
            height=self.height,
            target=ProcessName.STREAM_MANAGER
        )
        self.ipc.send_message(msg)
    
    def _send_heartbeat(self):
        """发送心跳（包含FPS信息）"""
        self.ipc.send(
            msg_type=MessageType.HEARTBEAT,
            target=ProcessName.SUPERVISOR,
            data={
                'fps': self.current_fps,
                'frame_count': self.frame_count
            }
        )
    
    def _cleanup(self):
        """清理资源"""
        try:
            if self.frame_buffer:
                self.frame_buffer.cleanup()
                logger.info("已清理共享内存")
        except Exception as e:
            logger.error(f"清理共享内存失败: {e}")
