"""
音频异常检测器
使用 YamNet 模型对音频进行分类检测
"""

import time
import threading
import os
import numpy as np
from typing import Optional
from queue import Queue, Empty
from datetime import datetime
from utils.logger import setup_logger

# 导入音频文件保存库
try:
    from scipy.io import wavfile
    SCIPY_AVAILABLE = True
except ImportError:
    try:
        import soundfile as sf
        SCIPY_AVAILABLE = False
    except ImportError:
        sf = None
        SCIPY_AVAILABLE = None

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
        self.yamnet = YamNetLoader(model_path)
        self.classifier = EventClassifier(
            class_names_path='models/yamnet_class_map.csv',
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
        
        # 保存音频到logs文件夹用于调试
        #self._save_audio_for_debug(audio_data, timestamp)
        
        try:
            # YamNet 推理
            scores = self.yamnet.predict(audio_data)
            
            if scores is None:
                logger.error("YamNet 推理失败")
                return None
            
            # 获取 Top-5 预测
            top_predictions = self.yamnet.get_top_predictions(scores, top_k=5)
            
            # 添加详细的调试日志
            logger.debug(f"音频数据 - 长度: {len(audio_data)}, 范围: [{audio_data.min():.3f}, {audio_data.max():.3f}]")
            logger.debug(f"YamNet 输出 shape: {scores.shape}")
            logger.debug(f"YamNet Top-5 预测: {top_predictions}")
            
            # 事件分类
            event_result = self.classifier.classify(top_predictions)
            logger.debug(f"事件分类结果: {event_result}")
            
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
    
    def _save_audio_for_debug(self, audio_data: np.ndarray, timestamp: float):
        """
        保存音频数据到logs文件夹用于调试
        
        Args:
            audio_data: 音频数据
            timestamp: 时间戳
        """
        try:
            # 创建logs目录
            logs_dir = 'logs/audio_debug'
            os.makedirs(logs_dir, exist_ok=True)
            
            # 生成文件名（使用时间戳）
            dt = datetime.fromtimestamp(timestamp)
            filename = f"{dt.strftime('%Y%m%d_%H%M%S_%f')[:-3]}.wav"
            filepath = os.path.join(logs_dir, filename)
            
            # 保存wav文件
            sample_rate = 16000  # YamNet使用16kHz采样率
            
            if SCIPY_AVAILABLE is True:
                # 使用scipy保存
                # 将float32数据转换为int16格式
                audio_int16 = (audio_data * 32767).astype(np.int16)
                wavfile.write(filepath, sample_rate, audio_int16)
            elif SCIPY_AVAILABLE is False and sf is not None:
                # 使用soundfile保存
                sf.write(filepath, audio_data, sample_rate)
            else:
                # 没有可用的库，跳过保存
                if self.total_detections == 1:
                    logger.warning("未安装scipy或soundfile，无法保存调试音频")
                return
            
            logger.debug(f"已保存调试音频: {filepath}")
            
        except Exception as e:
            logger.error(f"保存调试音频失败: {e}")
    
    def get_statistics(self) -> dict:
        """获取检测统计信息"""
        anomaly_rate = self.anomaly_count / max(self.total_detections, 1) * 100
        
        return {
            'total_detections': self.total_detections,
            'anomaly_count': self.anomaly_count,
            'anomaly_rate': f"{anomaly_rate:.2f}%",
            'queue_size': self.detection_queue.qsize()
        }
