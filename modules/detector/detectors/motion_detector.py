"""
运动检测器（Pipeline第1级）
使用OpenCV进行帧差法检测画面是否有运动
只有检测到运动时才继续后续检测，大幅节省资源
"""

import cv2
import numpy as np
from typing import Dict, Any
from .base import BaseDetector, DetectionResult
from utils.logger import setup_logger

logger = setup_logger('motion_detector')


class MotionDetector(BaseDetector):
    """
    运动检测器 - Pipeline第1级
    
    策略：
    1. 使用背景差分法检测运动区域
    2. 如果运动区域面积超过阈值，则认为有活动
    3. 只有检测到运动时返回 should_continue=True
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config, name="MotionDetector")
        
        # 配置参数
        self.min_area = config.get('min_area', 500)  # 最小运动区域面积
        self.blur_size = config.get('blur_size', 21)  # 高斯模糊核大小
        self.threshold = config.get('threshold', 25)  # 二值化阈值
        self.use_background_subtractor = config.get('use_background_subtractor', True)
        
        # 背景模型
        self.background_subtractor = None
        self.prev_frame = None
        
        logger.info(f"运动检测器初始化: min_area={self.min_area}, threshold={self.threshold}")
    
    def initialize(self) -> bool:
        """初始化背景减除器"""
        try:
            if self.use_background_subtractor:
                # 使用MOG2背景减除算法（更鲁棒）
                self.background_subtractor = cv2.createBackgroundSubtractorMOG2(
                    history=500,
                    varThreshold=16,
                    detectShadows=False
                )
            logger.info("✅ 运动检测器初始化成功")
            return True
        except Exception as e:
            logger.error(f"运动检测器初始化失败: {e}")
            return False
    
    def detect(self, frame, metadata: Dict[str, Any]) -> DetectionResult:
        """
        检测画面是否有运动
        
        Returns:
            should_continue=True: 检测到运动，继续后续检测
            should_continue=False: 画面静止，跳过后续检测
        """
        try:
            # 转换为灰度图
            gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
            gray = cv2.GaussianBlur(gray, (self.blur_size, self.blur_size), 0)
            
            if self.use_background_subtractor and self.background_subtractor:
                # 方法1：背景减除法（更准确）
                motion_detected, motion_area = self._detect_with_background_subtraction(gray)
            else:
                # 方法2：帧差法（更快速）
                motion_detected, motion_area = self._detect_with_frame_difference(gray)
            
            if motion_detected:
                logger.info(f"✅ 检测到运动（面积: {motion_area} px²）")
                return DetectionResult(
                    should_continue=True,
                    detections=[],  # 运动检测器不输出具体目标
                    metadata={'motion_area': motion_area, 'has_motion': True}
                )
            else:
                # 画面静止，早停
                return DetectionResult(
                    should_continue=False,
                    detections=[],
                    metadata={'has_motion': False}
                )
        
        except Exception as e:
            logger.error(f"运动检测失败: {e}")
            # 出错时继续检测（保守策略）
            return DetectionResult(should_continue=True)
    
    def _detect_with_background_subtraction(self, gray) -> tuple:
        """使用背景减除法"""
        fg_mask = self.background_subtractor.apply(gray)
        
        # 形态学操作去除噪声
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel)
        
        # 计算运动区域面积
        motion_area = cv2.countNonZero(fg_mask)
        motion_detected = motion_area > self.min_area
        
        return motion_detected, motion_area
    
    def _detect_with_frame_difference(self, gray) -> tuple:
        """使用帧差法"""
        if self.prev_frame is None:
            self.prev_frame = gray
            return False, 0
        
        # 计算帧差
        frame_diff = cv2.absdiff(self.prev_frame, gray)
        _, thresh = cv2.threshold(frame_diff, self.threshold, 255, cv2.THRESH_BINARY)
        
        # 膨胀操作连接相邻区域
        kernel = np.ones((5, 5), np.uint8)
        thresh = cv2.dilate(thresh, kernel, iterations=2)
        
        # 计算运动区域
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        motion_area = sum(cv2.contourArea(c) for c in contours)
        
        # 更新前一帧
        self.prev_frame = gray
        
        motion_detected = motion_area > self.min_area
        return motion_detected, motion_area
    
    def cleanup(self):
        """清理资源"""
        self.background_subtractor = None
        self.prev_frame = None
