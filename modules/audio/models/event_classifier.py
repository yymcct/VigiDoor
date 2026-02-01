"""
事件分类器
将 YamNet 的 521 类输出映射到业务关心的异常事件
"""

from enum import Enum
from typing import Optional, List, Tuple
import numpy as np
from utils.logger import setup_logger

logger = setup_logger('event_classifier')


class AudioEventType(Enum):
    """音频事件类型"""
    GLASS_BREAKING = "glass_breaking"    # 玻璃破碎
    SCREAM = "scream"                    # 呼救声/尖叫
    ALARM = "alarm"                      # 警报声
    EXPLOSION = "explosion"              # 爆炸声
    GUNSHOT = "gunshot"                  # 枪声
    DOG_BARK = "dog_bark"                # 狗叫（可选）
    NORMAL = "normal"                    # 正常声音


class EventClassifier:
    """
    事件分类器
    
    将 YamNet 的 AudioSet 521 类别映射到业务事件
    
    参考 AudioSet 类别表：
    https://research.google.com/audioset/ontology/index.html
    """
    
    # AudioSet 类别 ID 到业务事件的映射
    # 注意：这些 ID 需要根据实际的 YamNet 类别映射文件调整
    EVENT_MAPPING = {
        AudioEventType.GLASS_BREAKING: [
            311,  # Glass shatter
            312,  # Glass break
        ],
        AudioEventType.SCREAM: [
            250,  # Scream
            251,  # Shout
            367,  # Crying, sobbing
        ],
        AudioEventType.ALARM: [
            388,  # Alarm
            389,  # Smoke detector, smoke alarm
            390,  # Fire alarm
            391,  # Siren
        ],
        AudioEventType.EXPLOSION: [
            425,  # Explosion
            426,  # Burst, pop
        ],
        AudioEventType.GUNSHOT: [
            427,  # Gunshot, gunfire
            428,  # Machine gun
        ],
        AudioEventType.DOG_BARK: [
            74,   # Bark
            75,   # Howl
        ],
    }
    
    def __init__(
        self,
        class_names_path: Optional[str] = None,
        confidence_threshold: float = 0.3,
        enable_dog_bark: bool = False
    ):
        """
        初始化事件分类器
        
        Args:
            class_names_path: YamNet 类别名称文件路径（可选）
            confidence_threshold: 置信度阈值
            enable_dog_bark: 是否启用狗叫检测
        """
        self.confidence_threshold = confidence_threshold
        self.enable_dog_bark = enable_dog_bark
        
        # 加载类别名称（可选）
        self.class_names = self._load_class_names(class_names_path)
        
        # 构建反向映射：class_id -> event_type
        self.class_to_event = {}
        for event_type, class_ids in self.EVENT_MAPPING.items():
            if event_type == AudioEventType.DOG_BARK and not enable_dog_bark:
                continue
            for class_id in class_ids:
                self.class_to_event[class_id] = event_type
        
        logger.info(f"事件分类器初始化")
        logger.info(f"  置信度阈值: {confidence_threshold}")
        logger.info(f"  监控事件: {len(self.class_to_event)} 个类别")
    
    def _load_class_names(self, path: Optional[str]) -> Optional[List[str]]:
        """加载 YamNet 类别名称"""
        if path is None:
            return None
        
        try:
            with open(path, 'r') as f:
                class_names = [line.strip() for line in f]
            logger.info(f"加载了 {len(class_names)} 个类别名称")
            return class_names
        except Exception as e:
            logger.warning(f"加载类别名称失败: {e}")
            return None
    
    def classify(
        self,
        predictions: List[Tuple[int, float]]
    ) -> Optional[Tuple[AudioEventType, float, int]]:
        """
        对 YamNet 预测结果进行事件分类
        
        Args:
            predictions: [(class_id, score), ...] 列表
            
        Returns:
            (event_type, confidence, class_id) 或 None（无异常事件）
        """
        for class_id, score in predictions:
            # 检查是否属于关注的事件
            if class_id not in self.class_to_event:
                continue
            
            # 检查置信度
            if score < self.confidence_threshold:
                continue
            
            # 找到异常事件
            event_type = self.class_to_event[class_id]
            
            logger.info(f"🚨 检测到异常事件: {event_type.value}")
            logger.info(f"  置信度: {score:.3f}")
            logger.info(f"  类别 ID: {class_id}")
            
            if self.class_names and class_id < len(self.class_names):
                logger.info(f"  类别名称: {self.class_names[class_id]}")
            
            return (event_type, score, class_id)
        
        return None
    
    def get_event_description(self, event_type: AudioEventType) -> str:
        """获取事件的中文描述"""
        descriptions = {
            AudioEventType.GLASS_BREAKING: "玻璃破碎",
            AudioEventType.SCREAM: "呼救声/尖叫",
            AudioEventType.ALARM: "警报声",
            AudioEventType.EXPLOSION: "爆炸声",
            AudioEventType.GUNSHOT: "枪声",
            AudioEventType.DOG_BARK: "狗叫",
            AudioEventType.NORMAL: "正常声音",
        }
        return descriptions.get(event_type, "未知事件")
