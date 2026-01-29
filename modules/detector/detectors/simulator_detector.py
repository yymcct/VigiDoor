"""
模拟检测器（测试用）
用于在没有真实模型时进行功能测试
"""

import numpy as np
from typing import Dict, Any
from .base import BaseDetector, DetectionResult
from utils.logger import setup_logger

logger = setup_logger('simulator_detector')


class SimulatorDetector(BaseDetector):
    """
    模拟检测器 - 用于测试
    
    随机生成检测结果，模拟真实检测器的行为
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config, name="SimulatorDetector")
        
        self.detection_probability = config.get('detection_probability', 0.1)
        self.target_class = config.get('target_class', 0)
        self.target_class_name = config.get('target_class_name', 'person')
        
        logger.info(f"模拟检测器初始化: 检测概率={self.detection_probability}")
    
    def detect(self, frame, metadata: Dict[str, Any]) -> DetectionResult:
        """模拟检测"""
        # 按概率生成检测结果
        if np.random.rand() < self.detection_probability:
            detections = [{
                'class': self.target_class,
                'class_name': self.target_class_name,
                'confidence': 0.80 + np.random.rand() * 0.20,
                'bbox': [
                    0.3 + np.random.rand() * 0.2,  # x
                    0.3 + np.random.rand() * 0.2,  # y
                    0.15 + np.random.rand() * 0.15,  # w
                    0.25 + np.random.rand() * 0.25   # h
                ],
                'detector': 'simulator'
            }]
            
            logger.debug(f"模拟检测到 {len(detections)} 个目标")
            
            return DetectionResult(
                should_continue=True,
                detections=detections,
                metadata={'simulator_count': len(detections)}
            )
        else:
            return DetectionResult(
                should_continue=False,
                detections=[],
                metadata={'simulator_count': 0}
            )
