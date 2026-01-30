"""
YOLO检测器（Pipeline第2级）
使用YOLO模型进行目标检测，识别人形等目标
"""

import os
import cv2
import numpy as np
from typing import Dict, Any
from .base import BaseDetector, DetectionResult
from utils.logger import setup_logger

logger = setup_logger('yolo_detector')


class YOLODetector(BaseDetector):
    """
    YOLO检测器 - Pipeline第2级
    
    功能：
    1. 加载YOLO模型
    2. 检测指定类别的目标（人、车等）
    3. 过滤低置信度目标
    4. 返回归一化坐标（方便后续处理）
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config, name="YOLODetector")
        
        # 配置参数
        self.model_path = config.get('model_path', 'models/yolov8n.pt')
        self.confidence_threshold = config.get('confidence_threshold', 0.5)
        self.target_classes = config.get('target_classes', [0])  # 默认只检测人(class 0)
        self.input_size = config.get('input_size', 640)
        
        # 模型对象
        self.model = None
        
        logger.info(f"YOLO检测器初始化: model={self.model_path}, conf={self.confidence_threshold}")
    
    def initialize(self) -> bool:
        """加载YOLO模型"""
        try:
            # 检查模型文件
            if not os.path.exists(self.model_path):
                logger.error(f"模型文件不存在: {self.model_path}")
                return False
            
            # 尝试加载ultralytics
            try:
                from ultralytics import YOLO
                self.model = YOLO(self.model_path)
                
                # 模型预热
                logger.info("YOLO模型预热中...")
                dummy_frame = np.zeros((self.input_size, self.input_size, 3), dtype=np.uint8)
                self.model(dummy_frame, verbose=False)
                
                logger.info("✅ YOLO模型加载成功")
                return True
                
            except ImportError:
                logger.error("ultralytics未安装，无法使用YOLO检测器")
                return False
                
        except Exception as e:
            logger.error(f"YOLO模型加载失败: {e}")
            return False
    
    def detect(self, frame, metadata: Dict[str, Any]) -> DetectionResult:
        """
        执行YOLO检测
        
        Returns:
            检测到目标时返回 should_continue=True
            未检测到目标时返回 should_continue=False（提前结束pipeline）
        """
        try:
            if self.model is None:
                logger.error("YOLO模型未加载，跳过检测")
                return DetectionResult(
                    should_continue=False,
                    detections=[],
                    metadata={'yolo_error': 'model_not_loaded'}
                )
            
            # 降采样到YOLO输入尺寸
            frame_resized = cv2.resize(frame, (self.input_size, self.input_size))
            
            # YOLO推理
            results = self.model(frame_resized, verbose=False)
            
            # 解析结果
            detections = []
            for result in results:
                boxes = result.boxes
                
                for box in boxes:
                    cls = int(box.cls[0])
                    conf = float(box.conf[0])
                    
                    # 过滤目标类别和置信度
                    if cls in self.target_classes and conf >= self.confidence_threshold:
                        # 获取归一化坐标（相对于输入尺寸）
                        x1, y1, x2, y2 = box.xyxyn[0].tolist()
                        
                        detections.append({
                            'class': cls,
                            'class_name': self.model.names[cls],
                            'confidence': conf,
                            'bbox': [x1, y1, x2 - x1, y2 - y1],  # [x, y, w, h] 归一化
                            'detector': 'yolo'
                        })
            
            if detections:
                logger.info(f"✅ YOLO检测到 {len(detections)} 个目标")
                return DetectionResult(
                    should_continue=True,  # 检测到目标，继续区域判断
                    detections=detections,
                    metadata={'yolo_count': len(detections)}
                )
            else:
                # 未检测到目标，早停
                logger.info("YOLO未检测到目标，跳过后续检测")
                return DetectionResult(
                    should_continue=False,
                    detections=[],
                    metadata={'yolo_count': 0}
                )
        
        except Exception as e:
            logger.error(f"YOLO检测失败: {e}")
            # 出错时继续检测（保守策略）
            return DetectionResult(should_continue=True)
    
    def cleanup(self):
        """清理资源"""
        self.model = None
