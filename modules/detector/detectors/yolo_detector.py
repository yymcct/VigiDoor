"""
YOLO检测器（Pipeline第2级）
使用YOLO模型进行目标检测，识别人形等目标

推理后端优先级：
  1. ONNX Runtime（.onnx 文件）—— 最快，无 PyTorch 开销
  2. ultralytics（.pt 文件）     —— 兼容 fallback
"""

import os
import cv2
import numpy as np
from typing import Dict, Any, Optional
from .base import BaseDetector, DetectionResult
from utils.logger import setup_logger

logger = setup_logger('yolo_detector')

# COCO 人体关键点数量（yolo-pose 输出每人 17 个关键点 x 3）
_POSE_KPT_DIM = 3
_POSE_KPT_NUM = 17

# COCO class names（yolo11n-pose 只有一个类别: person）
_COCO_NAMES = {0: 'person'}


def _nms(boxes: np.ndarray, scores: np.ndarray, iou_thresh: float = 0.45) -> list:
    """简单 NMS，boxes 为 [N, 4] xyxy 格式（归一化）"""
    if len(boxes) == 0:
        return []
    x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    areas = (x2 - x1) * (y2 - y1)
    order = scores.argsort()[::-1]
    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(int(i))
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        inter = np.maximum(0, xx2 - xx1) * np.maximum(0, yy2 - yy1)
        iou = inter / (areas[i] + areas[order[1:]] - inter + 1e-6)
        order = order[1:][iou <= iou_thresh]
    return keep


class YOLODetector(BaseDetector):
    """
    YOLO检测器 - Pipeline第2级

    优先使用 ONNX Runtime 进行推理（比 PyTorch 快 3~5x），
    若模型文件为 .pt 则自动 fallback 到 ultralytics。
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config, name="YOLODetector")

        self.model_path = config.get('model_path', 'models/yolo11n-pose.pt')
        self.confidence_threshold = config.get('confidence_threshold', 0.5)
        self.target_classes = config.get('target_classes', [0])
        self.input_size = config.get('input_size', 320)

        # 运行时对象
        self._ort_session = None   # onnxruntime 会话
        self._ul_model = None      # ultralytics 模型（fallback）
        self._backend: Optional[str] = None  # 'onnx' | 'ultralytics'

        logger.info(f"YOLO检测器初始化: model={self.model_path}, "
                    f"conf={self.confidence_threshold}, input_size={self.input_size}")

    # ------------------------------------------------------------------
    # 初始化
    # ------------------------------------------------------------------

    def initialize(self) -> bool:
        """按优先级加载模型：先找同名 .onnx，再用原始 .pt"""
        onnx_path = self._resolve_onnx_path()
        if onnx_path and self._load_onnx(onnx_path):
            return True
        return self._load_ultralytics(self.model_path)

    def _resolve_onnx_path(self) -> Optional[str]:
        """将 .pt 路径转换为同目录的 .onnx 路径，若存在则返回"""
        base = os.path.splitext(self.model_path)[0]
        onnx_path = base + '.onnx'
        if os.path.exists(onnx_path):
            return onnx_path
        # model_path 本身就是 .onnx
        if self.model_path.endswith('.onnx') and os.path.exists(self.model_path):
            return self.model_path
        return None

    def _load_onnx(self, path: str) -> bool:
        try:
            import onnxruntime as ort
            # 优先使用多线程 CPU Provider，限制线程数以不抢占其他进程
            opts = ort.SessionOptions()
            opts.intra_op_num_threads = 2
            opts.inter_op_num_threads = 1
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            self._ort_session = ort.InferenceSession(
                path, sess_options=opts, providers=['CPUExecutionProvider']
            )
            # 从模型元数据读取真实输入尺寸，自动覆盖配置值，避免不匹配
            inp = self._ort_session.get_inputs()[0]
            _, _, model_h, model_w = inp.shape
            if isinstance(model_h, int) and isinstance(model_w, int):
                if self.input_size != model_h:
                    logger.warning(f"input_size 配置为 {self.input_size}，模型实际需要 {model_h}，已自动修正")
                    self.input_size = model_h
            # 预热
            dummy = np.zeros((1, 3, self.input_size, self.input_size), dtype=np.float32)
            self._ort_session.run(None, {inp.name: dummy})
            self._backend = 'onnx'
            logger.info(f"✅ ONNX Runtime 模型加载成功: {path}  input_size={self.input_size}")
            return True
        except Exception as e:
            logger.warning(f"ONNX 加载失败，将尝试 ultralytics fallback: {e}")
            self._ort_session = None
            return False

    def _load_ultralytics(self, path: str) -> bool:
        if not os.path.exists(path):
            logger.error(f"模型文件不存在: {path}")
            return False
        try:
            from ultralytics import YOLO
            self._ul_model = YOLO(path)
            dummy = np.zeros((self.input_size, self.input_size, 3), dtype=np.uint8)
            self._ul_model(dummy, verbose=False)
            self._backend = 'ultralytics'
            logger.info(f"✅ ultralytics 模型加载成功（fallback）: {path}")
            return True
        except ImportError:
            logger.error("ultralytics 未安装，YOLO 检测器不可用")
            return False
        except Exception as e:
            logger.error(f"ultralytics 模型加载失败: {e}")
            return False

    # ------------------------------------------------------------------
    # 检测入口
    # ------------------------------------------------------------------

    def detect(self, frame, metadata: Dict[str, Any]) -> DetectionResult:
        if self._backend is None:
            logger.error("YOLO 模型未加载")
            return DetectionResult(should_continue=False, detections=[],
                                   metadata={'yolo_error': 'model_not_loaded'})
        try:
            if self._backend == 'onnx':
                detections = self._detect_onnx(frame)
            else:
                detections = self._detect_ultralytics(frame)

            if detections:
                logger.info(f"✅ YOLO检测到 {len(detections)} 个目标 [{self._backend}]")
                return DetectionResult(should_continue=True, detections=detections,
                                       metadata={'yolo_count': len(detections)})
            else:
                logger.debug("YOLO未检测到目标，早停")
                return DetectionResult(should_continue=False, detections=[],
                                       metadata={'yolo_count': 0})
        except Exception as e:
            logger.error(f"YOLO检测失败: {e}")
            return DetectionResult(should_continue=True)

    # ------------------------------------------------------------------
    # ONNX 推理（核心快路径）
    # ------------------------------------------------------------------

    def _preprocess(self, frame: np.ndarray) -> np.ndarray:
        """BGR → RGB → resize → normalize → NCHW float32"""
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb, (self.input_size, self.input_size))
        blob = resized.astype(np.float32) / 255.0
        return blob.transpose(2, 0, 1)[np.newaxis]  # (1, 3, H, W)

    def _detect_onnx(self, frame: np.ndarray) -> list:
        """
        yolo11n-pose ONNX 输出形状: (1, 56, 2100)
          前 4 维: cx, cy, w, h（归一化）
          第 4 维: objectness * class_conf (person)
          后 51 维: 17 关键点 × 3 (x, y, conf)
        """
        blob = self._preprocess(frame)
        input_name = self._ort_session.get_inputs()[0].name
        output = self._ort_session.run(None, {input_name: blob})[0]  # (1, 56, N)

        # 统一转为 (N, 56)
        preds = output[0].T  # (2100, 56)

        detections = []
        conf_col = 4  # yolo11-pose: 第5列为 person 置信度

        # 批量过滤低置信度
        scores = preds[:, conf_col]
        mask = scores >= self.confidence_threshold
        if not mask.any():
            return []

        filtered = preds[mask]
        filtered_scores = scores[mask]

        # cx, cy, w, h → x1, y1, x2, y2（归一化）
        cx, cy, w, h = filtered[:, 0], filtered[:, 1], filtered[:, 2], filtered[:, 3]
        x1 = cx - w / 2
        y1 = cy - h / 2
        x2 = cx + w / 2
        y2 = cy + h / 2
        boxes_xyxy = np.stack([x1, y1, x2, y2], axis=1)

        keep = _nms(boxes_xyxy, filtered_scores)

        for idx in keep:
            row = filtered[idx]
            score = float(filtered_scores[idx])
            bx1, by1, bx2, by2 = float(x1[idx]), float(y1[idx]), float(x2[idx]), float(y2[idx])

            det: Dict[str, Any] = {
                'class': 0,
                'class_name': 'person',
                'confidence': score,
                'bbox': [bx1, by1, bx2 - bx1, by2 - by1],  # [x, y, w, h] 归一化
                'detector': 'yolo_onnx',
            }

            # 关键点（若有）
            if filtered.shape[1] > 5:
                kpt_raw = row[5:].reshape(_POSE_KPT_NUM, _POSE_KPT_DIM)
                det['keypoints'] = kpt_raw.tolist()

            detections.append(det)

        return detections

    # ------------------------------------------------------------------
    # ultralytics fallback
    # ------------------------------------------------------------------

    def _detect_ultralytics(self, frame: np.ndarray) -> list:
        frame_resized = cv2.resize(frame, (self.input_size, self.input_size))
        results = self._ul_model(frame_resized, verbose=False)
        detections = []
        for result in results:
            boxes = result.boxes
            keypoints = getattr(result, 'keypoints', None)
            kpts_xyn = kpts_conf = None
            if keypoints is not None:
                try:
                    kpts_xyn = keypoints.xyn
                    kpts_conf = keypoints.conf
                except Exception:
                    pass

            for idx, box in enumerate(boxes):
                cls = int(box.cls[0])
                conf = float(box.conf[0])
                if cls in self.target_classes and conf >= self.confidence_threshold:
                    x1, y1, x2, y2 = box.xyxyn[0].tolist()
                    det: Dict[str, Any] = {
                        'class': cls,
                        'class_name': self._ul_model.names[cls],
                        'confidence': conf,
                        'bbox': [x1, y1, x2 - x1, y2 - y1],
                        'detector': 'yolo',
                    }
                    if kpts_xyn is not None and idx < len(kpts_xyn):
                        try:
                            kpts = kpts_xyn[idx].tolist()
                            if kpts_conf is not None and idx < len(kpts_conf):
                                confs = kpts_conf[idx].tolist()
                                for i, c in enumerate(confs):
                                    if i < len(kpts) and len(kpts[i]) >= 2:
                                        if len(kpts[i]) == 2:
                                            kpts[i].append(float(c))
                                        else:
                                            kpts[i][2] = float(c)
                            det['keypoints'] = kpts
                        except Exception:
                            pass
                    detections.append(det)
        return detections

    # ------------------------------------------------------------------

    def cleanup(self):
        self._ort_session = None
        self._ul_model = None
        self._backend = None
