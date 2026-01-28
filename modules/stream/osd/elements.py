"""
OSD 渲染元素模块
提供可组合的 OSD 元素，支持时间戳、检测框、设备信息等
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Any
import numpy as np
import cv2


class OSDElement(ABC):
    """
    OSD 元素抽象基类
    
    所有 OSD 元素必须实现这个接口
    """
    
    @abstractmethod
    def render(self, frame: np.ndarray, **kwargs) -> np.ndarray:
        """
        在帧上渲染 OSD 元素
        
        Args:
            frame: 输入帧
            **kwargs: 额外参数
            
        Returns:
            np.ndarray: 渲染后的帧
        """
        pass


class TimestampElement(OSDElement):
    """
    时间戳元素
    显示当前时间
    """
    
    def __init__(
        self,
        position: tuple = (20, 40),
        font_scale: float = 0.8,
        color: tuple = (255, 255, 255),
        thickness: int = 2,
        format: str = '%Y-%m-%d %H:%M:%S'
    ):
        """
        Args:
            position: 文字位置 (x, y)
            font_scale: 字体大小
            color: 颜色 (R, G, B)
            thickness: 线条粗细
            format: 时间格式
        """
        self.position = position
        self.font_scale = font_scale
        self.color = color
        self.thickness = thickness
        self.format = format
    
    def render(self, frame: np.ndarray, **kwargs) -> np.ndarray:
        """渲染时间戳"""
        timestamp = kwargs.get('timestamp', datetime.now().timestamp())
        time_str = datetime.fromtimestamp(timestamp).strftime(self.format)
        
        cv2.putText(
            frame, time_str, self.position,
            cv2.FONT_HERSHEY_SIMPLEX,
            self.font_scale, self.color, self.thickness
        )
        
        return frame


class DeviceInfoElement(OSDElement):
    """
    设备信息元素
    显示设备 ID 等信息
    """
    
    def __init__(
        self,
        device_id: str,
        position: tuple = None,  # None 表示自动定位到左下角
        font_scale: float = 0.6,
        color: tuple = (255, 255, 255),
        thickness: int = 1
    ):
        """
        Args:
            device_id: 设备 ID
            position: 文字位置 (x, y)，None 表示自动定位
            font_scale: 字体大小
            color: 颜色 (R, G, B)
            thickness: 线条粗细
        """
        self.device_id = device_id
        self.position = position
        self.font_scale = font_scale
        self.color = color
        self.thickness = thickness
    
    def render(self, frame: np.ndarray, **kwargs) -> np.ndarray:
        """渲染设备信息"""
        text = f"Device: {self.device_id}"
        
        # 自动定位到左下角
        if self.position is None:
            height = frame.shape[0]
            position = (20, height - 20)
        else:
            position = self.position
        
        cv2.putText(
            frame, text, position,
            cv2.FONT_HERSHEY_SIMPLEX,
            self.font_scale, self.color, self.thickness
        )
        
        return frame


class DetectionBoxElement(OSDElement):
    """
    检测框元素
    绘制 AI 检测结果的边界框和标签
    """
    
    def __init__(
        self,
        box_thickness: int = 2,
        text_font_scale: float = 0.5,
        text_thickness: int = 2
    ):
        """
        Args:
            box_thickness: 边框粗细
            text_font_scale: 标签字体大小
            text_thickness: 标签线条粗细
        """
        self.box_thickness = box_thickness
        self.text_font_scale = text_font_scale
        self.text_thickness = text_thickness
        
        # 状态对应的颜色
        self.state_colors = {
            'alarm': (0, 0, 255),    # 红色
            'alert': (0, 255, 255),  # 黄色
            'safe': (0, 255, 0)      # 绿色
        }
    
    def render(self, frame: np.ndarray, **kwargs) -> np.ndarray:
        """渲染检测框"""
        detections = kwargs.get('detections', [])
        state = kwargs.get('state', 'safe')
        
        # 选择颜色
        color = self.state_colors.get(state, (0, 255, 0))
        
        height, width = frame.shape[:2]
        
        for det in detections:
            # 归一化坐标 → 像素坐标
            bbox = det.get('bbox', [])
            if len(bbox) != 4:
                continue
            
            x, y, w, h = bbox
            x1 = int(x * width)
            y1 = int(y * height)
            x2 = int((x + w) * width)
            y2 = int((y + h) * height)
            
            # 绘制矩形
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, self.box_thickness)
            
            # 绘制标签
            class_name = det.get('class_name', 'unknown')
            confidence = det.get('confidence', 0.0)
            label = f"{class_name} {confidence:.2f}"
            
            cv2.putText(
                frame, label, (x1, max(y1 - 10, 15)),
                cv2.FONT_HERSHEY_SIMPLEX,
                self.text_font_scale, color, self.text_thickness
            )
        
        return frame


class CompositeOSDElement(OSDElement):
    """
    组合 OSD 元素
    可以包含多个子元素，按顺序渲染
    """
    
    def __init__(self, elements: List[OSDElement]):
        """
        Args:
            elements: OSD 元素列表
        """
        self.elements = elements
    
    def render(self, frame: np.ndarray, **kwargs) -> np.ndarray:
        """依次渲染所有子元素"""
        for element in self.elements:
            frame = element.render(frame, **kwargs)
        return frame
    
    def add_element(self, element: OSDElement):
        """添加元素"""
        self.elements.append(element)
    
    def remove_element(self, element: OSDElement):
        """移除元素"""
        if element in self.elements:
            self.elements.remove(element)
