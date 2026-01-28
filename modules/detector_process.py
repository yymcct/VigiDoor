"""
AI 检测进程
负责视频分析和异常检测
"""

import time
import os
import numpy as np
from utils.logger import setup_logger
from core.ipc import IPCClient, MessageType
from core.ipc.registry import ProcessName
from utils.frame_buffer import SharedFrameBuffer

logger = setup_logger('ai_detector')


class AIDetectorProcess:
    """
    AI 检测进程 - 负责视频分析和异常检测（增强版）
    
    功能：
    1. 从共享内存读取原始RGB帧
    2. 降低检测频率（3 FPS），节省资源
    3. 使用 YOLO 进行目标检测
    4. 检测结果写入消息队列（供OSD进程使用）
    5. 检测框坐标归一化（方便缩放）
    6. 判断是否为异常事件并上报到 Supervisor
    """
    
    def __init__(self, ipc_client: IPCClient, shared_state, config):
        self.ipc = ipc_client
        self.state = shared_state
        self.config = config
        self.running = True
        
        # 配置参数
        self.confidence_threshold = config['ai_detector']['confidence_threshold']
        self.target_classes = config['ai_detector']['target_classes']
        self.detect_interval = config['ai_detector'].get('detect_interval', 8)  # 每N帧检测一次
        
        # 共享内存帧缓冲（读取者）
        self.frame_buffer = None
        
        # 检测统计
        self.last_frame_id = -1
        self.detection_count = 0
        
        logger.info(f"AI 检测进程初始化完成（增强版）")
        logger.info(f"  置信度阈值: {self.confidence_threshold}")
        logger.info(f"  目标类别: {self.target_classes}")
        logger.info(f"  检测间隔: 每 {self.detect_interval} 帧检测一次")
    
    def run(self):
        """主循环"""
        logger.info("🎥 AI 检测进程启动（增强版）")
        
        try:
            # 打开共享内存（读取者模式）
            self._init_shared_memory()
            
            # 加载 AI 模型
            model = self._init_model()
            
            last_heartbeat = time.time()
            check_interval = 0.1  # 检查新帧的间隔
            
            while self.running:
                try:
                    # 读取最新帧
                    frame_data = self.frame_buffer.read_frame(copy=True)
                    
                    if frame_data is None:
                        # 无有效帧，等待
                        time.sleep(check_interval)
                        continue
                    
                    frame, frame_id, timestamp = frame_data
                    
                    # 检查是否是新帧（避免重复检测）
                    if frame_id <= self.last_frame_id:
                        time.sleep(check_interval)
                        continue
                    
                    self.last_frame_id = frame_id
                    
                    # 判断是否需要检测（跳帧策略）
                    if not self._should_detect(frame_id):
                        time.sleep(check_interval)
                        continue
                    
                    # 执行AI检测
                    detections = self._detect(frame, model)
                    
                    # 发送检测结果
                    if detections:
                        self._publish_detection_result(frame_id, timestamp, detections)
                        
                        # 判断是否需要报警
                        if self._is_anomaly(detections):
                            self._report_anomaly(frame_id, timestamp, detections)
                    
                    self.detection_count += 1
                    
                    # 定期发送心跳
                    if time.time() - last_heartbeat > 10:
                        self.ipc.send_heartbeat()
                        last_heartbeat = time.time()
                    
                    # 检查关闭信号
                    msg = self.ipc.receive(timeout=0.001)
                    if msg and msg.get('type') == 'shutdown':
                        logger.info("收到关闭信号")
                        break
                
                except Exception as e:
                    logger.error(f"检测循环异常: {e}", exc_info=True)
                    time.sleep(1)
                    
        except KeyboardInterrupt:
            logger.info("检测到中断信号")
        finally:
            self._cleanup()
            logger.info("AI 检测进程退出")
    
    def _init_shared_memory(self):
        """初始化共享内存（读取者模式）"""
        try:
            # 等待共享内存创建（最多等待10秒）
            max_wait = 10
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                try:
                    self.frame_buffer = SharedFrameBuffer(
                        width=self.config['camera']['width'],
                        height=self.config['camera']['height'],
                        name=self.config['camera']['shared_memory_name'],
                        create=False  # 读取者模式
                    )
                    logger.info("✅ 共享内存连接成功")
                    return
                except FileNotFoundError:
                    logger.warning("等待共享内存创建...")
                    time.sleep(1)
            
            raise RuntimeError("共享内存连接超时")
            
        except Exception as e:
            logger.error(f"共享内存连接失败: {e}")
            raise
    
    def _should_detect(self, frame_id):
        """判断是否应该检测此帧（跳帧策略）"""
        # 根据系统状态动态调整检测频率
        system_state = self.state.get('global_state', 'safe')
        
        if system_state == 'alarm':
            # 报警状态：每帧都检测
            return True
        elif system_state == 'alert':
            # 警戒状态：每3帧检测一次
            return frame_id % 3 == 0
        else:
            # 安全状态：按配置的间隔检测
            return frame_id % self.detect_interval == 0
    
    def _init_model(self):
        """初始化AI模型"""
        try:
            # 尝试加载YOLO模型
            model_path = self.config['ai_detector']['model_path']
            
            if not os.path.exists(model_path):
                logger.warning(f"模型文件不存在: {model_path}，使用模拟模式")
                return None
            
            # 尝试导入ultralytics
            try:
                from ultralytics import YOLO
                model = YOLO(model_path)
                
                # 模型预热
                logger.info("YOLO模型预热中...")
                dummy_frame = np.zeros((640, 640, 3), dtype=np.uint8)
                model(dummy_frame, verbose=False)
                
                logger.info("✅ YOLO模型加载成功")
                return model
                
            except ImportError:
                logger.warning("ultralytics未安装，使用模拟模式")
                return None
                
        except Exception as e:
            logger.error(f"模型加载失败: {e}")
            return None
    
    def _detect(self, frame, model):
        """执行目标检测"""
        if model is None:
            # 模拟检测（测试用）
            return self._detect_simulation()
        
        try:
            # 降采样到640x640（YOLO标准输入尺寸）
            import cv2
            frame_resized = cv2.resize(frame, (640, 640))
            
            # YOLO推理
            results = model(frame_resized, verbose=False)
            
            # 解析结果
            detections = []
            for result in results:
                boxes = result.boxes
                
                for box in boxes:
                    cls = int(box.cls[0])
                    conf = float(box.conf[0])
                    
                    # 过滤目标类别和置信度
                    if cls in self.target_classes and conf >= self.confidence_threshold:
                        # 获取归一化坐标（相对于640x640）
                        x1, y1, x2, y2 = box.xyxyn[0].tolist()
                        
                        detections.append({
                            'class': cls,
                            'class_name': model.names[cls],
                            'confidence': conf,
                            'bbox': [x1, y1, x2 - x1, y2 - y1]  # [x, y, w, h] 归一化
                        })
            
            return detections
            
        except Exception as e:
            logger.error(f"检测失败: {e}")
            return []
    
    def _detect_simulation(self):
        """模拟检测（测试用）"""
        # 10% 概率模拟检测到目标
        if np.random.rand() < 0.1:
            return [{
                'class': 0,
                'class_name': 'person',
                'confidence': 0.85 + np.random.rand() * 0.15,
                'bbox': [
                    0.3 + np.random.rand() * 0.2,  # x
                    0.3 + np.random.rand() * 0.2,  # y
                    0.2 + np.random.rand() * 0.1,  # w
                    0.3 + np.random.rand() * 0.2   # h
                ]
            }]
        return []
    
    def _publish_detection_result(self, frame_id, timestamp, detections):
        """发布检测结果（供OSD进程使用）"""
        self.ipc.send_message({
            'type': 'detection_result',
            'to': 'stream_manager',  # 发送给流媒体进程用于OSD渲染
            'data': {
                'frame_id': frame_id,
                'timestamp': timestamp,
                'detections': detections
            }
        })
    
    def _is_anomaly(self, detections):
        """判断是否为异常事件"""
        # 简单策略：检测到任何目标类别即认为异常
        return len(detections) > 0
    
    def _report_anomaly(self, frame_id, timestamp, detections):
        """上报异常事件"""
        logger.warning(f"🚨 检测到异常！帧号: {frame_id}, 目标数: {len(detections)}")
        
        # 构造报警数据
        alarm_data = {
            'event_type': 'intrusion',
            'confidence': max(d['confidence'] for d in detections),
            'timestamp': timestamp,
            'frame_id': frame_id,
            'detections': detections,
            'snapshot_path': f"data/snapshots/alarm_{int(timestamp)}.jpg"
        }
        
        # 发送报警消息
        self.ipc.send_alarm(alarm_data)
    
    def _cleanup(self):
        """清理资源"""
        try:
            if self.frame_buffer:
                self.frame_buffer.close()
                logger.info("已关闭共享内存连接")
        except Exception as e:
            logger.error(f"清理资源失败: {e}")
