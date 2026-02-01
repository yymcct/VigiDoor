"""
音频异常检测器
使用 YamNet 模型对音频进行分类检测
"""

import time
import threading
import numpy as np
from typing import Optional
from queue import Queue, Empty
from utils.logger import setup_logger

from .models import YamNetLoader, EventClassifier, AudioEventType

logger = setup_logger('audio_detector')


class AudioAnomalyDetector:
    """
    音频异常检测器（YamNet）
    
    功能：
    1. 在独立线程中运行 YamNet 推理
    2. 识别玻璃破碎、呼救声、警报声等异常事件
    3. 异步检测，不阻塞主线程
    
    参数：
    - model_path: YamNet 模型文件路径
    - target_events: 关注的事件类型列表
    - confidence_threshold: 置信度阈值
    """
    
    def __init__(
        self,
        model_path: str,
        confidence_threshold: float = 0.4,
        enable_dog_bark: bool = False
    ):
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        
        # 初始化组件
        self.yamnet = YamNetLoader(model_path, use_tflite=True)
        self.classifier = EventClassifier(
            confidence_threshold=confidence_threshold,
            enable_dog_bark=enable_dog_bark
        )
        
        # 检测队列
        self.detection_queue = Queue(maxsize=10)
        
        # 线程控制
        self.running = False
        self.thread = None
        
        # 回调函数
        self.on_anomaly_detected = None
        
        # 统计
        self.total_detections = 0
        self.anomaly_count = 0
        
        logger.info(f"音频异常检测器初始化")
        logger.info(f"  模型路径: {model_path}")
        logger.info(f"  置信度阈值: {confidence_threshold}")
    
    def initialize(self) -> bool:
        """初始化检测器（加载模型）"""
        logger.info("正在加载 YamNet 模型...")
        
        if not self.yamnet.load():
            logger.error("YamNet 模型加载失败")
            return False
        
        logger.info("✅ 音频异常检测器初始化完成")
        return True
    
    def start(self) -> bool:
        """启动检测线程"""
        if self.running:
            logger.warning("检测线程已在运行")
            return False
        
        if self.yamnet.interpreter is None:
            logger.error("模型未加载，请先调用 initialize()")
            return False
        
        self.running = True
        self.thread = threading.Thread(
            target=self._detection_loop,
            daemon=True,
            name="AudioDetection"
        )
        self.thread.start()
        
        logger.info("✅ 音频检测线程已启动")
        return True
    
    def detect(self, audio_data: np.ndarray) -> None:
        """
        异步检测音频（将音频放入队列）
        
        Args:
            audio_data: 音频数据 (float32 NumPy数组)
        """
        try:
            self.detection_queue.put_nowait((time.time(), audio_data))
        except:
            logger.debug("检测队列已满，跳过此次检测")
    
    def _detection_loop(self):
        """检测线程主循环"""
        logger.info("检测线程运行中...")
        
        while self.running:
            try:
                # 从队列获取音频
                timestamp, audio_data = self.detection_queue.get(timeout=0.5)
                
                # 执行检测
                result = self._detect_sync(audio_data, timestamp)
                
                # 如果检测到异常，触发回调
                if result and self.on_anomaly_detected:
                    try:
                        self.on_anomaly_detected(result)
                    except Exception as e:
                        logger.error(f"回调函数异常: {e}")
                
            except Empty:
                continue
            except Exception as e:
                logger.error(f"检测循环异常: {e}", exc_info=True)
    
    def _detect_sync(self, audio_data: np.ndarray, timestamp: float) -> Optional[dict]:
        """
        同步检测音频
        
        Args:
            audio_data: 音频数据
            timestamp: 时间戳
            
        Returns:
            检测结果字典或 None
        """
        self.total_detections += 1
        
        start_time = time.time()
        
        try:
            # YamNet 推理
            scores = self.yamnet.predict(audio_data)
            
            if scores is None:
                logger.error("YamNet 推理失败")
                return None
            
            # 获取 Top-5 预测
            top_predictions = self.yamnet.get_top_predictions(scores, top_k=5)
            
            # 事件分类
            event_result = self.classifier.classify(top_predictions)
            
            inference_time = (time.time() - start_time) * 1000
            logger.debug(f"YamNet 推理耗时: {inference_time:.1f}ms")
            
            # 如果没有检测到异常事件
            if event_result is None:
                return None
            
            # 检测到异常
            event_type, confidence, class_id = event_result
            self.anomaly_count += 1
            
            result = {
                'event_type': event_type.value,
                'event_name': self.classifier.get_event_description(event_type),
                'confidence': confidence,
                'class_id': class_id,
                'timestamp': timestamp,
                'inference_time_ms': inference_time,
                'top_predictions': top_predictions[:3]  # 保存前3个预测
            }
            
            logger.warning(f"🚨 检测到音频异常: {result['event_name']}")
            logger.warning(f"  置信度: {confidence:.3f}")
            logger.warning(f"  推理耗时: {inference_time:.1f}ms")
            
            return result
            
        except Exception as e:
            logger.error(f"检测失败: {e}", exc_info=True)
            return None
    
    def stop(self):
        """停止检测线程"""
        if not self.running:
            return
        
        logger.info("正在停止音频检测...")
        self.running = False
        
        # 等待线程结束
        if self.thread:
            self.thread.join(timeout=2.0)
        
        logger.info("✅ 音频检测已停止")
    
    def get_statistics(self) -> dict:
        """获取检测统计信息"""
        anomaly_rate = self.anomaly_count / max(self.total_detections, 1) * 100
        
        return {
            'total_detections': self.total_detections,
            'anomaly_count': self.anomaly_count,
            'anomaly_rate': f"{anomaly_rate:.2f}%",
            'queue_size': self.detection_queue.qsize()
        }
