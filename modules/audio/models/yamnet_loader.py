"""
YamNet 模型加载器
负责加载和管理 YamNet 模型（TFLite 或 ONNX）
"""

import numpy as np
from pathlib import Path
from typing import Optional, Tuple
from utils.logger import setup_logger

logger = setup_logger('yamnet_loader')


class YamNetLoader:
    """
    YamNet 模型加载器
    
    YamNet 是 Google 开源的音频分类模型，可识别 521 种声音类别
    
    输入：16kHz 单声道音频波形
    输出：(batch_size, num_frames, 521) 的分类得分
    
    参考：https://github.com/tensorflow/models/tree/master/research/audioset/yamnet
    """
    
    def __init__(self, model_path: str, use_tflite: bool = True):
        """
        初始化 YamNet 加载器
        
        Args:
            model_path: 模型文件路径（.tflite 或 .onnx）
            use_tflite: 是否使用 TFLite（推荐树莓派使用）
        """
        self.model_path = Path(model_path)
        self.use_tflite = use_tflite
        
        # 模型参数
        self.sample_rate = 16000
        self.waveform_length = 15600  # 0.975 秒 @ 16kHz
        
        # 模型实例
        self.interpreter = None
        self.input_details = None
        self.output_details = None
        
        logger.info(f"YamNet 加载器初始化")
        logger.info(f"  模型路径: {self.model_path}")
        logger.info(f"  使用 TFLite: {use_tflite}")
    
    def load(self) -> bool:
        """加载模型"""
        if not self.model_path.exists():
            logger.error(f"模型文件不存在: {self.model_path}")
            logger.info("请下载 YamNet TFLite 模型：")
            logger.info("  wget https://tfhub.dev/google/lite-model/yamnet/classification/tflite/1?lite-format=tflite")
            logger.info("  mv yamnet.tflite models/")
            return False
        
        try:
            if self.use_tflite:
                return self._load_tflite()
            else:
                return self._load_onnx()
        except Exception as e:
            logger.error(f"加载模型失败: {e}", exc_info=True)
            return False
    
    def _load_tflite(self) -> bool:
        """加载 TensorFlow Lite 模型"""
        try:
            import tensorflow as tf
            
            # 加载 TFLite 模型
            self.interpreter = tf.lite.Interpreter(model_path=str(self.model_path))
            self.interpreter.allocate_tensors()
            
            # 获取输入输出详情
            self.input_details = self.interpreter.get_input_details()
            self.output_details = self.interpreter.get_output_details()
            
            logger.info("✅ TFLite 模型加载成功")
            logger.info(f"  输入形状: {self.input_details[0]['shape']}")
            logger.info(f"  输出形状: {self.output_details[0]['shape']}")
            
            return True
            
        except ImportError:
            logger.error("TensorFlow Lite 未安装")
            logger.info("安装命令: pip3 install tensorflow-lite")
            return False
        except Exception as e:
            logger.error(f"加载 TFLite 模型失败: {e}")
            return False
    
    def _load_onnx(self) -> bool:
        """加载 ONNX 模型"""
        try:
            import onnxruntime as ort
            
            # 加载 ONNX 模型
            self.interpreter = ort.InferenceSession(
                str(self.model_path),
                providers=['CPUExecutionProvider']
            )
            
            logger.info("✅ ONNX 模型加载成功")
            return True
            
        except ImportError:
            logger.error("ONNX Runtime 未安装")
            logger.info("安装命令: pip3 install onnxruntime")
            return False
        except Exception as e:
            logger.error(f"加载 ONNX 模型失败: {e}")
            return False
    
    def predict(self, waveform: np.ndarray) -> Optional[np.ndarray]:
        """
        对音频波形进行预测
        
        Args:
            waveform: 音频波形 (float32, shape: [samples])
            
        Returns:
            预测结果 (shape: [num_frames, 521]) 或 None
        """
        if self.interpreter is None:
            logger.error("模型未加载")
            return None
        
        try:
            # 预处理
            waveform = self._preprocess(waveform)
            
            # 推理
            if self.use_tflite:
                return self._predict_tflite(waveform)
            else:
                return self._predict_onnx(waveform)
                
        except Exception as e:
            logger.error(f"预测失败: {e}", exc_info=True)
            return None
    
    def _preprocess(self, waveform: np.ndarray) -> np.ndarray:
        """
        预处理音频波形
        
        Args:
            waveform: 原始音频
            
        Returns:
            处理后的音频
        """
        # 确保是 float32
        if waveform.dtype != np.float32:
            waveform = waveform.astype(np.float32)
        
        # 确保长度正确（填充或截断）
        if len(waveform) < self.waveform_length:
            # 填充零
            waveform = np.pad(waveform, (0, self.waveform_length - len(waveform)))
        elif len(waveform) > self.waveform_length:
            # 截断
            waveform = waveform[:self.waveform_length]
        
        # 归一化到 [-1, 1]
        max_val = np.max(np.abs(waveform))
        if max_val > 0:
            waveform = waveform / max_val
        
        return waveform
    
    def _predict_tflite(self, waveform: np.ndarray) -> np.ndarray:
        """使用 TFLite 进行预测"""
        # 设置输入
        self.interpreter.set_tensor(
            self.input_details[0]['index'],
            waveform.reshape(1, -1)
        )
        
        # 推理
        self.interpreter.invoke()
        
        # 获取输出
        scores = self.interpreter.get_tensor(self.output_details[0]['index'])
        
        return scores[0]  # 移除 batch 维度
    
    def _predict_onnx(self, waveform: np.ndarray) -> np.ndarray:
        """使用 ONNX 进行预测"""
        input_name = self.interpreter.get_inputs()[0].name
        outputs = self.interpreter.run(None, {input_name: waveform.reshape(1, -1)})
        
        return outputs[0][0]  # 移除 batch 维度
    
    def get_top_predictions(
        self,
        scores: np.ndarray,
        top_k: int = 5
    ) -> list[Tuple[int, float]]:
        """
        获取 Top-K 预测结果
        
        Args:
            scores: 预测得分 (shape: [num_frames, 521])
            top_k: 返回前K个结果
            
        Returns:
            [(class_id, score), ...] 列表
        """
        # 对所有帧取平均
        mean_scores = np.mean(scores, axis=0)
        
        # 获取 Top-K 索引
        top_indices = np.argsort(mean_scores)[-top_k:][::-1]
        
        # 返回 (class_id, score) 列表
        results = [(int(idx), float(mean_scores[idx])) for idx in top_indices]
        
        return results
