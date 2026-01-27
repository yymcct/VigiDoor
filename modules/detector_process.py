"""
AI 检测进程
负责视频分析和异常检测
"""

import time
import os
from utils.logger import setup_logger
from utils.ipc import IPCHelper

logger = setup_logger('ai_detector')


class AIDetectorProcess:
    """
    AI 检测进程 - 负责视频分析和异常检测
    
    功能：
    1. 从摄像头捕获视频帧
    2. 使用 YOLO 进行目标检测
    3. 判断是否为异常事件
    4. 上报异常到 Supervisor
    """
    
    def __init__(self, ipc_queue, shared_state, config):
        self.ipc = IPCHelper(ipc_queue, 'ai_detector')
        self.state = shared_state
        self.config = config
        self.running = True
        
        # 配置参数
        self.confidence_threshold = config['ai_detector']['confidence_threshold']
        self.target_classes = config['ai_detector']['target_classes']
        self.fps = config['ai_detector']['fps']
        
        logger.info(f"AI 检测进程初始化完成")
        logger.info(f"  置信度阈值: {self.confidence_threshold}")
        logger.info(f"  目标类别: {self.target_classes}")
    
    def run(self):
        """主循环"""
        logger.info("🎥 AI 检测进程启动")
        
        # 初始化摄像头
        camera = self._init_camera()
        if not camera:
            logger.error("摄像头初始化失败，进入模拟模式")
            self._run_simulation_mode()
            return
        
        # 加载 AI 模型（初版暂时跳过）
        # model = self._init_model()
        
        last_heartbeat = time.time()
        frame_count = 0
        
        try:
            while self.running:
                # 捕获帧（初版使用模拟）
                frame = self._capture_frame_simulation(camera)
                
                # 每 N 帧进行一次检测
                if frame_count % 3 == 0:
                    # AI 推理（初版跳过，直接模拟）
                    is_anomaly = self._detect_anomaly_simulation(frame_count)
                    
                    if is_anomaly:
                        self._report_anomaly(frame_count)
                
                frame_count += 1
                
                # 定期发送心跳
                if time.time() - last_heartbeat > 10:
                    self.ipc.send_heartbeat()
                    last_heartbeat = time.time()
                
                # 控制帧率
                time.sleep(1.0 / self.fps)
                
                # 检查关闭信号
                msg = self.ipc.receive(timeout=0.001)
                if msg and msg.get('type') == 'shutdown':
                    logger.info("收到关闭信号")
                    break
                    
        except KeyboardInterrupt:
            logger.info("检测到中断信号")
        finally:
            self._cleanup(camera)
            logger.info("AI 检测进程退出")
    
    def _init_camera(self):
        """初始化摄像头"""
        try:
            # 尝试使用 picamera2（树莓派）
            # from picamera2 import Picamera2
            # camera = Picamera2()
            # camera.configure(...)
            # camera.start()
            # return camera
            
            # 初版返回模拟对象
            logger.info("✅ 摄像头初始化成功（模拟模式）")
            return {'mode': 'simulation'}
            
        except Exception as e:
            logger.error(f"摄像头初始化失败: {e}")
            return None
    
    def _capture_frame_simulation(self, camera):
        """捕获帧（模拟）"""
        # 初版返回模拟帧
        return {'frame_id': int(time.time())}
    
    def _detect_anomaly_simulation(self, frame_count):
        """检测异常（模拟）"""
        # 初版：每 100 帧模拟一次异常
        return frame_count % 100 == 0
    
    def _report_anomaly(self, frame_count):
        """上报异常事件"""
        logger.warning(f"🚨 检测到异常！帧号: {frame_count}")
        
        alarm_data = {
            'event_type': 'intrusion',
            'confidence': 0.95,
            'timestamp': time.time(),
            'frame_id': frame_count,
            'snapshot_path': f"/tmp/alarm_{int(time.time())}.jpg"
        }
        
        self.ipc.send_alarm(alarm_data)
    
    def _run_simulation_mode(self):
        """模拟模式运行"""
        logger.info("进入模拟模式")
        
        while self.running:
            # 定期发送心跳
            self.ipc.send_heartbeat()
            time.sleep(10)
    
    def _cleanup(self, camera):
        """清理资源"""
        try:
            if camera and camera.get('mode') != 'simulation':
                # camera.stop()
                pass
        except:
            pass
