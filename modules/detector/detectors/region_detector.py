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
        self.keypoint_conf_threshold = config.get('keypoint_conf_threshold', 0.2)  # 关键点置信度阈值
        
        # 解析警戒区域
        self.parsed_regions = self._parse_regions(self.regions)
        
        logger.info(f"区域检测器初始化: {len(self.parsed_regions)} 个警戒区域")
        for i, region in enumerate(self.parsed_regions):
            logger.info(f"  区域 {i+1}: {region['name']} (类型: {region['type']})")
        logger.debug(f"关键点置信度阈值: {self.keypoint_conf_threshold}")
    
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
            logger.debug(f"RegionDetector: received {len(detections)} detections to check")
            if not detections:
                return DetectionResult(
                    should_continue=True,
                    detections=[],
                    metadata={}
                )
            
            # 检查每个检测目标是否入侵
            intrusion_detections = []
            
            for detection in detections:
                # 仅通过 bbox 与警戒区域判断入侵
                logger.debug(
                    f"RegionDetector: target={detection.get('class_name', 'unknown')}, "
                    f"conf={detection.get('confidence', 0):.2f}, "
                    f"has_bbox={bool(detection.get('bbox'))}"
                )
                is_intrusion, region_name = self._check_intrusion(detection)
                
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
                else:
                    logger.debug(
                        f"RegionDetector: no intrusion for target={detection.get('class_name', 'unknown')}, "
                        f"conf={detection.get('confidence', 0):.2f}"
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
    
    def _check_intrusion(self, detection: Dict[str, Any]) -> tuple:
        """
        检查检测目标是否入侵警戒区域（基于骨架关键点）
        
        Args:
            detection: 检测目标字典（应包含 keypoints）
        
        Returns:
            (is_intrusion, region_name)
        """
        # 仅基于 bbox 与警戒区域判断
        bbox = detection.get('bbox')
        if not bbox:
            logger.debug("RegionDetector: no bbox; skip")
            return False, None

        x, y, w, h = bbox
        center_x = x + w / 2
        center_y = y + h / 2
        logger.debug(
            f"RegionDetector: fallback bbox=({x:.3f},{y:.3f},{w:.3f},{h:.3f}), "
            f"center=({center_x:.3f},{center_y:.3f})"
        )

        for region in self.parsed_regions:
            if not region['enabled']:
                continue

            if region['type'] == 'rect':
                rx, ry, rw, rh = region['coords']

                if rx <= center_x <= rx + rw and ry <= center_y <= ry + rh:
                    logger.debug(
                        f"RegionDetector: bbox center hit rect region={region['name']}"
                    )
                    return True, region['name']

                overlap = self._calculate_rect_overlap(bbox, region['coords'])
                if overlap > self.overlap_threshold:
                    logger.debug(
                        f"RegionDetector: bbox overlap hit rect region={region['name']}, "
                        f"overlap={overlap:.3f}"
                    )
                    return True, region['name']

            elif region['type'] == 'polygon':
                if self._point_in_polygon(center_x, center_y, region['coords']):
                    logger.debug(
                        f"RegionDetector: bbox center hit polygon region={region['name']}"
                    )
                    return True, region['name']

                if self._bbox_intersects_polygon(bbox, region['coords']):
                    logger.debug(
                        f"RegionDetector: bbox intersect polygon region={region['name']}"
                    )
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

    def _bbox_intersects_polygon(self, bbox: List[float], polygon: List[List[float]]) -> bool:
        """
        判断 bbox 是否与多边形相交/重叠
        规则：
        1) bbox 任一角点在多边形内
        2) 多边形任一顶点在 bbox 内
        3) bbox 任一边与多边形边相交
        """
        x, y, w, h = bbox
        if w <= 0 or h <= 0:
            return False

        # 1) bbox corners in polygon
        corners = [
            (x, y),
            (x + w, y),
            (x + w, y + h),
            (x, y + h),
        ]
        for cx, cy in corners:
            if self._point_in_polygon(cx, cy, polygon):
                return True

        # 2) polygon vertices in bbox
        for px, py in polygon:
            if x <= px <= x + w and y <= py <= y + h:
                return True

        # 3) edge intersection
        bbox_edges = [
            ((x, y), (x + w, y)),
            ((x + w, y), (x + w, y + h)),
            ((x + w, y + h), (x, y + h)),
            ((x, y + h), (x, y)),
        ]
        poly_edges = []
        n = len(polygon)
        for i in range(n):
            p1 = polygon[i]
            p2 = polygon[(i + 1) % n]
            poly_edges.append((tuple(p1), tuple(p2)))

        for e1 in bbox_edges:
            for e2 in poly_edges:
                if self._segments_intersect(e1[0], e1[1], e2[0], e2[1]):
                    return True

        return False

    def _segments_intersect(
        self,
        p1: tuple,
        p2: tuple,
        q1: tuple,
        q2: tuple,
    ) -> bool:
        """判断线段是否相交（含端点）"""

        def _orient(a, b, c):
            return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

        def _on_segment(a, b, c):
            return (
                min(a[0], b[0]) <= c[0] <= max(a[0], b[0])
                and min(a[1], b[1]) <= c[1] <= max(a[1], b[1])
            )

        o1 = _orient(p1, p2, q1)
        o2 = _orient(p1, p2, q2)
        o3 = _orient(q1, q2, p1)
        o4 = _orient(q1, q2, p2)

        if o1 == 0 and _on_segment(p1, p2, q1):
            return True
        if o2 == 0 and _on_segment(p1, p2, q2):
            return True
        if o3 == 0 and _on_segment(q1, q2, p1):
            return True
        if o4 == 0 and _on_segment(q1, q2, p2):
            return True

        return (o1 > 0) != (o2 > 0) and (o3 > 0) != (o4 > 0)
