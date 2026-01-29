"""
检测器工厂
根据配置创建检测器实例
"""

from typing import Dict, Any, List
from .base import BaseDetector
from .motion_detector import MotionDetector
from .yolo_detector import YOLODetector
from .region_detector import RegionDetector
from .simulator_detector import SimulatorDetector
from utils.logger import setup_logger

logger = setup_logger('detector_factory')


# 检测器注册表
DETECTOR_REGISTRY = {
    'motion': MotionDetector,
    'yolo': YOLODetector,
    'region': RegionDetector,
    'simulator': SimulatorDetector,
}


def create_detector(detector_type: str, config: Dict[str, Any]) -> BaseDetector:
    """
    创建单个检测器实例
    
    Args:
        detector_type: 检测器类型 ('motion', 'yolo', 'region', 'simulator')
        config: 检测器配置
    
    Returns:
        BaseDetector: 检测器实例
    
    Raises:
        ValueError: 未知的检测器类型
    """
    if detector_type not in DETECTOR_REGISTRY:
        raise ValueError(
            f"未知的检测器类型: {detector_type}. "
            f"可用类型: {list(DETECTOR_REGISTRY.keys())}"
        )
    
    detector_class = DETECTOR_REGISTRY[detector_type]
    return detector_class(config)


def create_detector_pipeline(pipeline_config: List[Dict[str, Any]]) -> List[BaseDetector]:
    """
    创建检测器Pipeline
    
    Args:
        pipeline_config: Pipeline配置列表，每个元素包含:
            - type: 检测器类型
            - enabled: 是否启用
            - config: 检测器配置
    
    Returns:
        List[BaseDetector]: 检测器列表（按顺序）
    
    Example:
        pipeline_config = [
            {'type': 'motion', 'enabled': True, 'config': {...}},
            {'type': 'yolo', 'enabled': True, 'config': {...}},
            {'type': 'region', 'enabled': True, 'config': {...}},
        ]
    """
    detectors = []
    
    for i, stage in enumerate(pipeline_config):
        detector_type = stage.get('type')
        enabled = stage.get('enabled', True)
        config = stage.get('config', {})
        
        if not enabled:
            logger.info(f"跳过禁用的检测器: {detector_type}")
            continue
        
        try:
            # 添加enabled标志到config
            config['enabled'] = enabled
            
            # 创建检测器
            detector = create_detector(detector_type, config)
            detectors.append(detector)
            
            logger.info(f"✅ 创建检测器 [{i+1}]: {detector}")
            
        except Exception as e:
            logger.error(f"创建检测器失败 [{i+1}] {detector_type}: {e}")
            # 继续创建其他检测器
    
    if not detectors:
        logger.warning("⚠️ 没有启用的检测器，将使用模拟检测器")
        detectors.append(SimulatorDetector({'enabled': True}))
    
    return detectors


def register_detector(name: str, detector_class: type):
    """
    注册自定义检测器
    
    Args:
        name: 检测器名称
        detector_class: 检测器类（继承自BaseDetector）
    """
    if not issubclass(detector_class, BaseDetector):
        raise TypeError(f"{detector_class} 必须继承自 BaseDetector")
    
    DETECTOR_REGISTRY[name] = detector_class
    logger.info(f"注册自定义检测器: {name} -> {detector_class.__name__}")
