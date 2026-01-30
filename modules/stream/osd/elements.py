"""
OSD 渲染元素模块
提供可组合的 OSD 元素，支持时间戳、检测框、设备信息等
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Any
from pathlib import Path
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont
from utils.logger import setup_logger

logger = setup_logger('osd_elements')

_FONT_CACHE: Dict[int, ImageFont.FreeTypeFont] = {}
_FONT_WARNING_EMITTED = False

# 项目内字体（你稍后可替换文件名）
_DEFAULT_FONT_FILENAME = 'wqy-microhei.ttc'
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_PROJECT_FONT_PATH = _PROJECT_ROOT / 'fonts' / _DEFAULT_FONT_FILENAME


def _load_font(font_size: int) -> ImageFont.FreeTypeFont:
    """优先加载项目 ./fonts 下的字体，失败则回退系统字体。"""
    global _FONT_WARNING_EMITTED

    if font_size in _FONT_CACHE:
        return _FONT_CACHE[font_size]

    font = None

    # 1) 项目内字体优先
    if _PROJECT_FONT_PATH.exists():
        try:
            font = ImageFont.truetype(str(_PROJECT_FONT_PATH), font_size)
        except (OSError, IOError):
            font = None

    # 2) 默认字体
    if font is None:
        font = ImageFont.load_default()
        if not _FONT_WARNING_EMITTED:
            logger.warning("⚠️ 未找到中文字体，使用默认字体")
            _FONT_WARNING_EMITTED = True

    _FONT_CACHE[font_size] = font
    return font


def put_chinese_text(
    img: np.ndarray,
    text: str,
    position: tuple,
    font_size: int = 20,
    color: tuple = (255, 255, 255)
) -> np.ndarray:
    """
    在图像上绘制中文文本（使用 PIL）
    
    Args:
        img: OpenCV 图像（BGR格式）
        text: 要绘制的文本
        position: 文本位置 (x, y)
        font_size: 字体大小
        color: 文字颜色 (R, G, B) 注意：传入RGB格式
        
    Returns:
        np.ndarray: 绘制后的图像
    """
    # 转换为 PIL Image（RGB格式）
    img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil)
    
    # 加载字体（优先项目 ./fonts 下的字体）
    try:
        font = _load_font(font_size)
    except Exception as e:
        logger.warning(f"⚠️ 加载字体失败: {e}，使用默认字体")
        font = ImageFont.load_default()
    
    # 绘制文本（PIL使用RGB颜色）
    draw.text(position, text, font=font, fill=color)
    
    # 转换回 OpenCV 格式（BGR）
    img_cv = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
    
    return img_cv


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
    
    def __init__(self, elements: List[OSDElement] = None):
        """
        支持两种初始化方式：
        1. 传入自定义元素列表
        2. 不传参数，自动从 ConfigManager 获取配置并创建默认元素
        
        Args:
            elements: OSD 元素列表（可选）
                     如果不提供，则自动从 ConfigManager 创建默认元素组合
        """
        if elements is not None:
            # 使用自定义元素
            self.elements = elements
        else:
            # 从 ConfigManager 自动创建默认元素
            self.elements = self._create_default_elements()
    
    def _create_default_elements(self) -> List[OSDElement]:
        """
        从 ConfigManager 获取配置并创建默认 OSD 元素组合
        
        Returns:
            List[OSDElement]: OSD 元素列表
        """
        try:
            from utils.config import ConfigManager
            config = ConfigManager.get_instance()
            device_id = config.device.id
            logger.info(f"✅ 成功从 ConfigManager 获取设备 ID: {device_id}")
        except RuntimeError as e:
            # ConfigManager 未初始化
            logger.warning(f"⚠️ ConfigManager 未初始化: {e}")
            device_id = 'Unknown'
        except AttributeError as e:
            # 配置不存在
            logger.warning(f"⚠️ 配置属性不存在: {e}")
            device_id = 'Unknown'
        except Exception as e:
            # 其他异常
            logger.error(f"❌ 获取设备 ID 失败: {e}", exc_info=True)
            device_id = 'Unknown'
        
        logger.info(f"📝 创建 OSD 元素，使用设备 ID: {device_id}")
        
        return [
            TimestampElement(
                position=(20, 40),
                font_scale=0.8
            ),
            DeviceInfoElement(
                device_id=device_id,
                position=None  # 自动定位到左下角
            ),
            DetectionBoxElement(
                box_thickness=2,
                text_font_scale=0.5
            ),
            RegionOverlayElement(),
            SkeletonElement(
                line_thickness=2,
                keypoint_radius=3,
                confidence_threshold=0.5
            ),
            FootTrafficElement(
                position=None,  # 自动定位到右上角
                font_scale=0.8
            )
        ]
    
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


class SkeletonElement(OSDElement):
    """
    人体骨架元素
    绘制人体关键点和骨架连线（用于姿态估计）
    """
    
    # COCO格式的骨架连接关系（17个关键点）
    SKELETON_CONNECTIONS = [
        (0, 1), (0, 2),      # 鼻子到眼睛
        (1, 3), (2, 4),      # 眼睛到耳朵
        (0, 5), (0, 6),      # 鼻子到肩膀
        (5, 7), (7, 9),      # 左臂
        (6, 8), (8, 10),     # 右臂
        (5, 6),              # 肩膀连线
        (5, 11), (6, 12),    # 肩膀到髋部
        (11, 13), (13, 15),  # 左腿
        (12, 14), (14, 16),  # 右腿
        (11, 12)             # 髋部连线
    ]
    
    def __init__(
        self,
        line_thickness: int = 2,
        keypoint_radius: int = 3,
        confidence_threshold: float = 0.5
    ):
        """
        Args:
            line_thickness: 骨架线条粗细
            keypoint_radius: 关键点半径
            confidence_threshold: 关键点置信度阈值
        """
        self.line_thickness = line_thickness
        self.keypoint_radius = keypoint_radius
        self.confidence_threshold = confidence_threshold
        
        # 彩虹色系（用于不同的骨架连接）
        self.colors = [
            (255, 0, 0), (255, 85, 0), (255, 170, 0), (255, 255, 0),
            (170, 255, 0), (85, 255, 0), (0, 255, 0), (0, 255, 85),
            (0, 255, 170), (0, 255, 255), (0, 170, 255), (0, 85, 255),
            (0, 0, 255), (85, 0, 255), (170, 0, 255), (255, 0, 255),
            (255, 0, 170)
        ]
    
    def render(self, frame: np.ndarray, **kwargs) -> np.ndarray:
        """渲染人体骨架"""
        detections = kwargs.get('detections', [])
        
        height, width = frame.shape[:2]
        
        for det in detections:
            keypoints = det.get('keypoints', [])
            
            if not keypoints:
                continue
            
            # 转换关键点坐标（归一化 → 像素）
            kpts_pixel = []
            for kpt in keypoints:
                if len(kpt) >= 3:  # [x, y, confidence]
                    x, y, conf = kpt[0], kpt[1], kpt[2]
                    
                    # 过滤低置信度关键点
                    if conf < self.confidence_threshold:
                        kpts_pixel.append(None)
                        continue
                    
                    px = int(x * width)
                    py = int(y * height)
                    kpts_pixel.append((px, py, conf))
                else:
                    kpts_pixel.append(None)
            
            # 绘制骨架连线
            for i, (start_idx, end_idx) in enumerate(self.SKELETON_CONNECTIONS):
                if start_idx >= len(kpts_pixel) or end_idx >= len(kpts_pixel):
                    continue
                
                start_kpt = kpts_pixel[start_idx]
                end_kpt = kpts_pixel[end_idx]
                
                if start_kpt is None or end_kpt is None:
                    continue
                
                # 绘制连线
                color = self.colors[i % len(self.colors)]
                cv2.line(
                    frame,
                    (start_kpt[0], start_kpt[1]),
                    (end_kpt[0], end_kpt[1]),
                    color,
                    self.line_thickness
                )
            
            # 绘制关键点
            for kpt in kpts_pixel:
                if kpt is None:
                    continue
                
                cv2.circle(
                    frame,
                    (kpt[0], kpt[1]),
                    self.keypoint_radius,
                    (0, 255, 0),  # 绿色关键点
                    -1  # 填充
                )
        
        return frame


class RegionOverlayElement(OSDElement):
    """
    区域叠加元素
    在画面上绘制检测区域框（从配置文件读取）
    """
    
    def __init__(self):
        """
        不需要传递参数，直接从 ConfigManager 读取配置
        从 ai_detector.pipeline 中获取 type=region 的检测器配置
        """
        self.regions = []
        self.region_config = None
        
        try:
            from utils.config import ConfigManager
            config = ConfigManager.get_instance()
            
            # 使用 get_raw() 方法获取原始 pipeline 配置
            pipeline = config.get_raw('ai_detector.pipeline')
            
            if pipeline and isinstance(pipeline, list):
                logger.info(f"🔍 找到 {len(pipeline)} 个 pipeline 阶段")
                
                # 从 pipeline 中查找 type=region 的检测器
                for detector in pipeline:
                    detector_type = detector.get('type')
                    detector_enabled = detector.get('enabled', False)
                    logger.info(f"  - 检测器类型: {detector_type}, 启用: {detector_enabled}")
                    
                    if detector_type == 'region' and detector_enabled:
                        self.region_config = detector.get('config', {})
                        self.regions = self.region_config.get('regions', [])
                        logger.info(f"✅ 成功从 ai_detector.pipeline 加载 {len(self.regions)} 个区域")
                        break
            else:
                logger.warning(f"⚠️ pipeline 配置为空或格式错误: {type(pipeline)}")
            
            if not self.regions:
                logger.warning("⚠️ 未找到启用的区域检测器配置")
                
        except RuntimeError as e:
            # ConfigManager未初始化，使用空配置
            import warnings
            warnings.warn(f"⚠️ ConfigManager 未初始化: {e}", RuntimeWarning)
        except Exception as e:
            # 其他错误
            import warnings
            warnings.warn(f"⚠️ 加载配置失败: {e}", RuntimeWarning)
    
    def render(self, frame: np.ndarray, **kwargs) -> np.ndarray:
        """渲染区域框"""
        if not self.regions:
            return frame
        
        height, width = frame.shape[:2]
        overlay = frame.copy()
        
        # 使用固定样式（原来从 osd_config 读取）
        color = (255, 255, 0)  # 黄色 (BGR)
        thickness = 2
        font_scale = 0.5
        alpha = 0.3
        
        for region in self.regions:
            if not region.get('enabled', True):
                continue
            
            region_type = region.get('type')
            region_name = region.get('name', 'Unknown')
            region_coords = region.get('coords', [])
            
            if region_type == 'rect' and len(region_coords) == 4:
                # 绘制矩形
                x, y, w, h = region_coords
                x1, y1 = int(x * width), int(y * height)
                x2, y2 = int((x + w) * width), int((y + h) * height)
                
                cv2.rectangle(
                    overlay, (x1, y1), (x2, y2),
                    color, thickness
                )
                
                # 绘制标签（支持中文）
                label_y = max(y1 - 20, 15)
                overlay = put_chinese_text(
                    overlay, region_name, (x1, label_y),
                    font_size=int(font_scale * 30),  # 转换为像素大小
                    color=(color[2], color[1], color[0])  # BGR -> RGB
                )
            
            elif region_type == 'polygon' and len(region_coords) >= 3:
                # 绘制多边形
                points = np.array([
                    [int(p[0] * width), int(p[1] * height)]
                    for p in region_coords
                ], dtype=np.int32)
                
                cv2.polylines(
                    overlay, [points], True,
                    color, thickness
                )
                
                # 绘制标签在第一个点附近（支持中文）
                p0 = region_coords[0]
                label_x = int(p0[0] * width)
                label_y = int(p0[1] * height)
                label_y = max(label_y - 10, 15)
                overlay = put_chinese_text(
                    overlay, region_name, (label_x, label_y),
                    font_size=int(font_scale * 20),  # 转换为像素大小
                    color=(color[2], color[1], color[0])  # BGR -> RGB
                )
        
        # 半透明叠加
        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
        
        return frame


class FootTrafficElement(OSDElement):
    """
    客流统计元素
    在画面上显示进出人数统计（后期功能）
    """
    
    def __init__(
        self,
        position: tuple = None,  # None表示自动定位到右上角
        font_scale: float = 1.0,
        color: tuple = (255, 255, 255),
        thickness: int = 2,
        bg_color: tuple = (0, 0, 0),
        bg_alpha: float = 0.6
    ):
        """
        Args:
            position: 显示位置 (x, y)，None表示自动定位
            font_scale: 字体大小
            color: 文字颜色 (R, G, B)
            thickness: 线条粗细
            bg_color: 背景颜色 (R, G, B)
            bg_alpha: 背景透明度 (0-1)
        """
        self.position = position
        self.font_scale = font_scale
        self.color = color
        self.thickness = thickness
        self.bg_color = bg_color
        self.bg_alpha = bg_alpha
    
    def render(self, frame: np.ndarray, **kwargs) -> np.ndarray:
        """渲染客流统计信息"""
        statistics = kwargs.get('statistics', {})
        
        # 获取统计数据
        in_count = statistics.get('in_count', 0)
        out_count = statistics.get('out_count', 0)
        current_count = statistics.get('current_count', 0)
        
        # 如果没有数据，不渲染
        if in_count == 0 and out_count == 0:
            return frame
        
        # 构建显示文本
        lines = [
            f"IN:  {in_count}",
            f"OUT: {out_count}",
            f"NOW: {current_count}"
        ]
        
        # 自动定位到右上角
        if self.position is None:
            height, width = frame.shape[:2]
            x = width - 200
            y = 40
        else:
            x, y = self.position
        
        # 计算文本区域大小
        line_height = int(30 * self.font_scale)
        max_width = 0
        
        for line in lines:
            (w, h), _ = cv2.getTextSize(
                line, cv2.FONT_HERSHEY_SIMPLEX,
                self.font_scale, self.thickness
            )
            max_width = max(max_width, w)
        
        # 绘制半透明背景
        overlay = frame.copy()
        cv2.rectangle(
            overlay,
            (x - 10, y - 30),
            (x + max_width + 10, y + len(lines) * line_height),
            self.bg_color,
            -1
        )
        cv2.addWeighted(overlay, self.bg_alpha, frame, 1 - self.bg_alpha, 0, frame)
        
        # 绘制文本
        for i, line in enumerate(lines):
            text_y = y + i * line_height
            cv2.putText(
                frame, line, (x, text_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                self.font_scale, self.color, self.thickness
            )
        
        return frame

