"""
检测器抽象基类
定义统一的检测接口，支持Pipeline早停机制
"""

from abc import ABC, abstractmethod
from typing import Tuple, List, Dict, Any


class DetectionResult:
    """检测结果封装类"""
    
    def __init__(self, 
                 should_continue: bool = True,
                 detections: List[Dict[str, Any]] = None,
                 metadata: Dict[str, Any] = None):
        """
        Args:
            should_continue: 是否继续执行后续检测器（False表示早停）
            detections: 检测到的目标列表
            metadata: 额外的元数据（传递给下一级检测器）
        """
        self.should_continue = should_continue
        self.detections = detections or []
        self.metadata = metadata or {}
    
    def merge(self, other: 'DetectionResult'):
        """合并另一个检测结果"""
        self.detections.extend(other.detections)
        self.metadata.update(other.metadata)


class BaseDetector(ABC):
    """
    检测器抽象基类
    
    所有检测器都应该继承此类并实现 detect() 方法
    支持Pipeline早停机制：当某一级检测器返回 should_continue=False 时，
    后续检测器将不再执行
    """
    
    def __init__(self, config: Dict[str, Any], name: str = None):
        """
        Args:
            config: 检测器配置
            name: 检测器名称（用于日志）
        """
        self.config = config
        self.name = name or self.__class__.__name__
        self.enabled = config.get('enabled', True)
    
    @abstractmethod
    def detect(self, frame, metadata: Dict[str, Any]) -> DetectionResult:
        """
        执行检测
        
        Args:
            frame: 输入图像帧 (numpy array, RGB格式)
            metadata: 上级检测器传递的元数据（如帧号、时间戳等）
        
        Returns:
            DetectionResult: 检测结果
                - should_continue: 是否继续后续检测
                - detections: 检测到的目标列表
                - metadata: 传递给下级的额外信息
        """
        pass
    
    def initialize(self) -> bool:
        """
        初始化检测器（加载模型等）
        
        Returns:
            bool: 是否初始化成功
        """
        return True
    
    def cleanup(self):
        """清理资源"""
        pass
    
    def __repr__(self):
        return f"{self.name}(enabled={self.enabled})"
