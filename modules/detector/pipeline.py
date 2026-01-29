"""
Pipeline管理器
按顺序执行检测器，支持早停机制
"""

from typing import List, Dict, Any
from .detectors.base import BaseDetector, DetectionResult
from utils.logger import setup_logger

logger = setup_logger('pipeline')


class DetectionPipeline:
    """
    检测Pipeline管理器
    
    功能：
    1. 按顺序执行多个检测器
    2. 支持早停机制（某一级返回should_continue=False时停止）
    3. 累积检测结果和元数据
    4. 统计每级检测器的执行情况
    """
    
    def __init__(self, detectors: List[BaseDetector]):
        """
        Args:
            detectors: 检测器列表（按执行顺序）
        """
        self.detectors = detectors
        self.stats = {
            'total_frames': 0,
            'early_stop_count': 0,
            'detector_stats': {}
        }
        
        logger.info(f"Pipeline初始化: {len(detectors)} 级检测器")
        for i, detector in enumerate(detectors):
            logger.info(f"  [{i+1}] {detector}")
            self.stats['detector_stats'][detector.name] = {
                'executed': 0,
                'detections': 0,
                'stopped': 0
            }
    
    def initialize(self) -> bool:
        """初始化所有检测器"""
        success = True
        
        for detector in self.detectors:
            try:
                if not detector.initialize():
                    logger.error(f"检测器初始化失败: {detector.name}")
                    success = False
            except Exception as e:
                logger.error(f"检测器初始化异常: {detector.name}, {e}")
                success = False
        
        return success
    
    def process(self, frame, metadata: Dict[str, Any] = None) -> DetectionResult:
        """
        处理一帧图像
        
        Args:
            frame: 输入图像帧
            metadata: 初始元数据（如帧号、时间戳）
        
        Returns:
            DetectionResult: 最终检测结果
        """
        self.stats['total_frames'] += 1
        
        # 初始化元数据
        if metadata is None:
            metadata = {}
        
        # 累积所有检测结果
        all_detections = []
        final_metadata = metadata.copy()
        
        # 按顺序执行检测器
        for i, detector in enumerate(self.detectors):
            if not detector.enabled:
                continue
            
            try:
                # 执行检测
                result = detector.detect(frame, final_metadata)
                
                # 更新统计
                stats = self.stats['detector_stats'][detector.name]
                stats['executed'] += 1
                stats['detections'] += len(result.detections)
                
                # 累积检测结果
                all_detections.extend(result.detections)
                final_metadata.update(result.metadata)
                
                # 检查是否早停
                if not result.should_continue:
                    logger.debug(f"Pipeline早停于第 {i+1} 级: {detector.name}")
                    self.stats['early_stop_count'] += 1
                    stats['stopped'] += 1
                    break
                
            except Exception as e:
                logger.error(f"检测器执行异常: {detector.name}, {e}", exc_info=True)
                # 继续执行下一个检测器
        
        # 将累积的检测结果放入metadata（供后续检测器使用）
        final_metadata['detections'] = all_detections
        
        return DetectionResult(
            should_continue=True,
            detections=all_detections,
            metadata=final_metadata
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """获取Pipeline统计信息"""
        stats = self.stats.copy()
        
        # 计算早停率
        if stats['total_frames'] > 0:
            stats['early_stop_rate'] = stats['early_stop_count'] / stats['total_frames']
        else:
            stats['early_stop_rate'] = 0.0
        
        return stats
    
    def reset_stats(self):
        """重置统计信息"""
        self.stats['total_frames'] = 0
        self.stats['early_stop_count'] = 0
        
        for detector_stats in self.stats['detector_stats'].values():
            detector_stats['executed'] = 0
            detector_stats['detections'] = 0
            detector_stats['stopped'] = 0
        
        logger.info("Pipeline统计已重置")
    
    def print_stats(self):
        """打印统计信息"""
        stats = self.get_stats()
        
        logger.info("=" * 60)
        logger.info("Pipeline 统计信息")
        logger.info("=" * 60)
        logger.info(f"总帧数: {stats['total_frames']}")
        logger.info(f"早停次数: {stats['early_stop_count']}")
        logger.info(f"早停率: {stats['early_stop_rate']:.1%}")
        logger.info("-" * 60)
        
        for detector_name, detector_stats in stats['detector_stats'].items():
            executed = detector_stats['executed']
            detections = detector_stats['detections']
            stopped = detector_stats['stopped']
            
            logger.info(f"{detector_name}:")
            logger.info(f"  执行次数: {executed}")
            logger.info(f"  检测目标数: {detections}")
            logger.info(f"  触发早停次数: {stopped}")
            
            if executed > 0:
                logger.info(f"  平均检测数/帧: {detections / executed:.2f}")
        
        logger.info("=" * 60)
    
    def cleanup(self):
        """清理所有检测器资源"""
        for detector in self.detectors:
            try:
                detector.cleanup()
            except Exception as e:
                logger.error(f"检测器清理失败: {detector.name}, {e}")
