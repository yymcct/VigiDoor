"""
区域入侵检测器（Pipeline第3级）
判断检测到的目标是否进入警戒区域
"""

import numpy as np
from typing import Dict, Any, List
from .base import BaseDetector, DetectionResult
from utils.logger import setup_logger

logger = setup_logger('region_detector')


class RegionDetector(BaseDetector):
    """
    区域入侵检测器 - Pipeline第3级
    
    功能：
    1. 定义警戒区域（支持多边形）
    2. 判断检测框是否进入警戒区域
    3. 标记入侵目标
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config, name="RegionDetector")
        
        # 配置参数
        self.regions = config.get('regions', [])  # 警戒区域列表
        self.overlap_threshold = config.get('overlap_threshold', 0.1)  # 重叠阈值
        
        # 解析警戒区域
        self.parsed_regions = self._parse_regions(self.regions)
        
        logger.info(f"区域检测器初始化: {len(self.parsed_regions)} 个警戒区域")
        for i, region in enumerate(self.parsed_regions):
            logger.info(f"  区域 {i+1}: {region['name']} (类型: {region['type']})")
    
    def _parse_regions(self, regions: List[Dict]) -> List[Dict]:
        """解析警戒区域配置"""
        parsed = []
        
        for region in regions:
            region_type = region.get('type', 'rect')
            
            if region_type == 'rect':
                # 矩形区域：[x, y, w, h] (归一化坐标)
                parsed.append({
                    'name': region.get('name', 'unnamed'),
                    'type': 'rect',
                    'coords': region['coords'],  # [x, y, w, h]
                    'enabled': region.get('enabled', True)
                })
            
            elif region_type == 'polygon':
                # 多边形区域：[[x1,y1], [x2,y2], ...] (归一化坐标)
                parsed.append({
                    'name': region.get('name', 'unnamed'),
                    'type': 'polygon',
                    'coords': region['coords'],  # list of [x, y]
                    'enabled': region.get('enabled', True)
                })
        
        return parsed
    
    def detect(self, frame, metadata: Dict[str, Any]) -> DetectionResult:
        """
        检查目标是否入侵警戒区域
        
        Note: 这是Pipeline最后一级，always return should_continue=True
        """
        try:
            # 从metadata中获取前置检测器的结果
            detections = metadata.get('detections', [])
            
            if not detections:
                return DetectionResult(
                    should_continue=True,
                    detections=[],
                    metadata={}
                )
            
            # 检查每个检测目标是否入侵
            intrusion_detections = []
            
            for detection in detections:
                bbox = detection['bbox']  # [x, y, w, h] 归一化
                
                # 检查是否进入任何警戒区域
                is_intrusion, region_name = self._check_intrusion(bbox)
                
                if is_intrusion:
                    # 标记为入侵目标
                    detection['is_intrusion'] = True
                    detection['intrusion_region'] = region_name
                    detection['detector'] = 'region'
                    intrusion_detections.append(detection)
                    
                    logger.warning(
                        f"🚨 检测到入侵！目标类型: {detection.get('class_name', 'unknown')}, "
                        f"区域: {region_name}, 置信度: {detection.get('confidence', 0):.2f}"
                    )
            
            if intrusion_detections:
                return DetectionResult(
                    should_continue=True,
                    detections=intrusion_detections,
                    metadata={'intrusion_count': len(intrusion_detections)}
                )
            else:
                # 有目标但未入侵
                return DetectionResult(
                    should_continue=True,
                    detections=[],
                    metadata={'intrusion_count': 0}
                )
        
        except Exception as e:
            logger.error(f"区域检测失败: {e}")
            return DetectionResult(should_continue=True)
    
    def _check_intrusion(self, bbox: List[float]) -> tuple:
        """
        检查边界框是否入侵警戒区域
        
        Args:
            bbox: [x, y, w, h] 归一化坐标
        
        Returns:
            (is_intrusion, region_name)
        """
        x, y, w, h = bbox
        
        # 计算边界框中心点
        center_x = x + w / 2
        center_y = y + h / 2
        
        for region in self.parsed_regions:
            if not region['enabled']:
                continue
            
            if region['type'] == 'rect':
                # 矩形区域判断
                rx, ry, rw, rh = region['coords']
                
                # 方法1：中心点在区域内
                if rx <= center_x <= rx + rw and ry <= center_y <= ry + rh:
                    return True, region['name']
                
                # 方法2：检查重叠面积
                overlap = self._calculate_rect_overlap(bbox, region['coords'])
                if overlap > self.overlap_threshold:
                    return True, region['name']
            
            elif region['type'] == 'polygon':
                # 多边形区域判断（点在多边形内）
                if self._point_in_polygon(center_x, center_y, region['coords']):
                    return True, region['name']
        
        return False, None
    
    def _calculate_rect_overlap(self, bbox1: List[float], bbox2: List[float]) -> float:
        """计算两个矩形的重叠比例（相对于bbox1）"""
        x1, y1, w1, h1 = bbox1
        x2, y2, w2, h2 = bbox2
        
        # 计算交集
        x_left = max(x1, x2)
        y_top = max(y1, y2)
        x_right = min(x1 + w1, x2 + w2)
        y_bottom = min(y1 + h1, y2 + h2)
        
        if x_right < x_left or y_bottom < y_top:
            return 0.0
        
        intersection_area = (x_right - x_left) * (y_bottom - y_top)
        bbox1_area = w1 * h1
        
        return intersection_area / bbox1_area if bbox1_area > 0 else 0.0
    
    def _point_in_polygon(self, x: float, y: float, polygon: List[List[float]]) -> bool:
        """
        射线法判断点是否在多边形内
        
        Args:
            x, y: 点坐标
            polygon: 多边形顶点列表 [[x1,y1], [x2,y2], ...]
        """
        n = len(polygon)
        inside = False
        
        p1x, p1y = polygon[0]
        for i in range(1, n + 1):
            p2x, p2y = polygon[i % n]
            
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            
            p1x, p1y = p2x, p2y
        
        return inside
