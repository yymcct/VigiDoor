"""
OSD 数据仓库
统一管理所有OSD渲染所需的数据，支持分类存储、过期管理、线程安全访问
"""

import time
import threading
from enum import Enum
from typing import Dict, List, Any, Optional
from utils.logger import setup_logger

logger = setup_logger('osd_data_store')


class OSDDataCategory(str, Enum):
    """
    OSD 数据类别枚举
    
    使用 str 类型的枚举，保证兼容性的同时提供类型安全
    """
    DETECTIONS = 'detections'      # AI检测结果（人形框、骨架等）
    STATISTICS = 'statistics'      # 统计数据（客流量等）
    ANNOTATIONS = 'annotations'    # 自定义标注
    METADATA = 'metadata'          # 元数据（状态、配置等）


class OSDDataStore:
    """
    OSD数据仓库
    
    职责：
    - 分类存储不同类型的渲染数据（detections、statistics、annotations等）
    - 数据过期管理（TTL机制）
    - 线程安全访问
    - 数据新鲜度检查
    
    设计理念：
    - 结构化：每种数据类型单独存储，避免混淆
    - 自动过期：避免渲染陈旧数据
    - 可扩展：添加新数据类型只需在_data字典中增加key
    """
    
    def __init__(self, ttl: float = 5.0):
        """
        初始化数据仓库
        
        Args:
            ttl: 数据存活时间（秒），超过此时间的数据视为过期
        """
        self._lock = threading.Lock()
        self._ttl = ttl
        
        # 分类存储数据
        self._data: Dict[str, Any] = {
            OSDDataCategory.DETECTIONS: [],       # AI检测结果（人形框、骨架等）
            OSDDataCategory.STATISTICS: {},       # 统计数据（客流量等）
            OSDDataCategory.ANNOTATIONS: [],      # 自定义标注
            OSDDataCategory.METADATA: {}          # 元数据（状态、配置等）
        }
        
        # 记录每个数据类别的最后更新时间
        self._timestamps: Dict[str, float] = {
            OSDDataCategory.DETECTIONS: 0.0,
            OSDDataCategory.STATISTICS: 0.0,
            OSDDataCategory.ANNOTATIONS: 0.0,
            OSDDataCategory.METADATA: 0.0
        }

        # 布撤防状态（持久字段，不受 TTL 影响）
        self._arm_status: bool = True

        logger.info(f"OSD数据仓库初始化完成，TTL={ttl}秒")
    
    def update_detections(self, detections: List[Dict[str, Any]]):
        """
        更新检测结果
        
        Args:
            detections: 检测结果列表，每项包含 {class, class_name, confidence, bbox, keypoints}
        """
        with self._lock:
            self._data[OSDDataCategory.DETECTIONS] = detections
            self._timestamps[OSDDataCategory.DETECTIONS] = time.time()
            
            logger.debug(f"更新检测结果：{len(detections)}个目标")
    
    def update_statistics(self, statistics: Dict[str, Any]):
        """
        更新统计数据（如客流量）
        
        Args:
            statistics: 统计数据字典，如 {in_count: 10, out_count: 8, total: 18}
        """
        with self._lock:
            self._data[OSDDataCategory.STATISTICS].update(statistics)
            self._timestamps[OSDDataCategory.STATISTICS] = time.time()
            
            logger.debug(f"更新统计数据：{statistics}")
    
    def update_annotations(self, annotations: List[Dict[str, Any]]):
        """
        更新自定义标注（如ROI区域、警戒线等）
        
        Args:
            annotations: 标注列表，每项包含 {type, geometry, label}
        """
        with self._lock:
            self._data[OSDDataCategory.ANNOTATIONS] = annotations
            self._timestamps[OSDDataCategory.ANNOTATIONS] = time.time()
            
            logger.debug(f"更新标注：{len(annotations)}个")
    
    def update_metadata(self, **metadata):
        """
        更新元数据（如系统状态、配置信息）
        
        Args:
            **metadata: 元数据键值对，如 state='alarm', mode='night'
        """
        with self._lock:
            self._data[OSDDataCategory.METADATA].update(metadata)
            self._timestamps[OSDDataCategory.METADATA] = time.time()
            
            logger.debug(f"更新元数据：{metadata}")
    
    def get_render_data(self) -> Dict[str, Any]:
        """
        获取所有有效的渲染数据（自动过滤过期数据）
        
        Returns:
            Dict: 包含所有未过期数据的字典
            {
                'detections': [...],      # 空列表或有效数据
                'statistics': {...},      # 空字典或有效数据
                'annotations': [...],     # 空列表或有效数据
                'metadata': {...}         # 空字典或有效数据
            }
        """
        with self._lock:
            current_time = time.time()
            result: Dict[str, Any] = {}
            
            for category in self._data:
                # 检查数据是否过期
                age = current_time - self._timestamps[category]
                
                key = category.value if isinstance(category, Enum) else category

                if age <= self._ttl:
                    # 数据有效，复制一份（避免外部修改）
                    if isinstance(self._data[category], list):
                        result[key] = self._data[category].copy()
                    elif isinstance(self._data[category], dict):
                        result[key] = self._data[category].copy()
                    else:
                        result[key] = self._data[category]
                else:
                    # 数据过期，返回空值
                    if isinstance(self._data[category], list):
                        result[key] = []
                    elif isinstance(self._data[category], dict):
                        result[key] = {}
                    else:
                        result[key] = None
            
            result['is_armed'] = self._arm_status
            return result
    
    def update_arm_status(self, is_armed: bool):
        """
        更新布撤防状态（不受 TTL 影响，永久生效）

        Args:
            is_armed: True 表示已布防，False 表示已撤防
        """
        with self._lock:
            self._arm_status = is_armed
            status_str = "已布防" if is_armed else "已撤防"
            logger.debug(f"布撤防状态更新: {status_str}")

    def is_data_fresh(self, category: str) -> bool:
        """
        检查指定类别的数据是否新鲜（未过期）
        
        Args:
            category: 数据类别名称
            
        Returns:
            bool: 数据新鲜返回True，过期或不存在返回False
        """
        with self._lock:
            if category not in self._timestamps:
                return False
            
            age = time.time() - self._timestamps[category]
            return age <= self._ttl
    
    def get_data_age(self, category: str) -> Optional[float]:
        """
        获取指定类别数据的年龄（秒）
        
        Args:
            category: 数据类别名称
            
        Returns:
            float: 数据年龄（秒），如果类别不存在返回None
        """
        with self._lock:
            if category not in self._timestamps:
                return None
            
            return time.time() - self._timestamps[category]
    
    def clear_category(self, category: str):
        """
        清空指定类别的数据
        
        Args:
            category: 数据类别名称
        """
        with self._lock:
            if category in self._data:
                if isinstance(self._data[category], list):
                    self._data[category] = []
                elif isinstance(self._data[category], dict):
                    self._data[category] = {}
                
                self._timestamps[category] = 0.0
                logger.debug(f"已清空数据类别：{category}")
    
    def clear_all(self):
        """清空所有数据"""
        with self._lock:
            for category in self._data:
                if isinstance(self._data[category], list):
                    self._data[category] = []
                elif isinstance(self._data[category], dict):
                    self._data[category] = {}
                
                self._timestamps[category] = 0.0
            
            logger.info("已清空所有OSD数据")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取数据仓库统计信息
        
        Returns:
            Dict: 统计信息，包括各类别数据量、年龄、新鲜度等
        """
        with self._lock:
            current_time = time.time()
            stats = {}
            
            for category in self._data:
                age = current_time - self._timestamps[category]
                is_fresh = age <= self._ttl
                
                if isinstance(self._data[category], list):
                    count = len(self._data[category])
                elif isinstance(self._data[category], dict):
                    count = len(self._data[category])
                else:
                    count = 1 if self._data[category] is not None else 0
                
                stats[category] = {
                    'count': count,
                    'age': round(age, 2),
                    'fresh': is_fresh,
                    'last_update': self._timestamps[category]
                }
            
            return stats
