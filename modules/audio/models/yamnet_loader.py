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
    YamNet 模型加载器（TFLite）
    
    YamNet 是 Google 开源的音频分类模型，可识别 521 种声音类别
    
    输入：16kHz 单声道音频波形
    输出：(batch_size, num_frames, 521) 的分类得分
    
    参考：https://github.com/tensorflow/models/tree/master/research/audioset/yamnet
    """
    
    def __init__(self, model_path: str):
        """
        初始化 YamNet 加载器
        
        Args:
            model_path: 模型文件路径（.tflite）
        """
        self.model_path = Path(model_path)
        
        # 模型参数
        self.sample_rate = 16000
        self.waveform_length = 15600  # 0.975 秒 @ 16kHz
        
        # 模型实例
        self.interpreter = None
        self.input_details = None
        self.output_details = None
        
        logger.info(f"YamNet 加载器初始化")
        logger.info(f"  模型路径: {self.model_path}")
    
    def load(self) -> bool:
        """加载模型"""
        if not self.model_path.exists():
            logger.error(f"模型文件不存在: {self.model_path}")
            logger.info("请下载 YamNet TFLite 模型：")
            logger.info("  wget https://tfhub.dev/google/lite-model/yamnet/classification/tflite/1?lite-format=tflite")
            logger.info("  mv yamnet.tflite models/")
            return False
        
        try:
            return self._load_tflite()
        except Exception as e:
            logger.error(f"加载模型失败: {e}", exc_info=True)
            return False
    
    def _load_tflite(self) -> bool:
        """加载 TensorFlow Lite 模型"""
        try:
            import tflite_runtime.interpreter as tflite
            
            # 加载 TFLite 模型
            self.interpreter = tflite.Interpreter(model_path=str(self.model_path))
            self.interpreter.allocate_tensors()
            
            # 获取输入输出详情
            self.input_details = self.interpreter.get_input_details()
            self.output_details = self.interpreter.get_output_details()
            
            # 记录期望的输入形状
            self.expected_input_shape = self.input_details[0]['shape']
            
            logger.info("✅ TFLite 模型加载成功")
            logger.info(f"  输入形状: {self.expected_input_shape}")
            logger.info(f"  输出形状: {self.output_details[0]['shape']}")
            logger.info(
                "  输入类型: %s, 量化参数: %s",
                self.input_details[0].get('dtype'),
                self.input_details[0].get('quantization')
            )
            logger.info(
                "  输出类型: %s, 量化参数: %s",
                self.output_details[0].get('dtype'),
                self.output_details[0].get('quantization')
            )
            
            return True
            
        except ImportError:
            logger.error("TensorFlow Lite 未安装")
            logger.info("安装命令: pip3 install tensorflow-lite")
            return False
        except Exception as e:
            logger.error(f"加载 TFLite 模型失败: {e}")
            return False
    
    def predict(self, waveform: np.ndarray, use_sliding_window: bool = False) -> Optional[np.ndarray]:
        """
        对音频波形进行预测
        
        Args:
            waveform: 音频波形 (float32, shape: [samples])
            use_sliding_window: 是否使用滑动窗口处理长音频（推荐！）
            
        Returns:
            预测结果 (shape: [num_frames, 521]) 或 None
        """
        if self.interpreter is None:
            logger.error("模型未加载")
            return None
        
        try:
            # 如果音频较长且启用滑动窗口，使用分段处理
            if use_sliding_window and len(waveform) > self.waveform_length:
                return self._predict_sliding_window(waveform)
            else:
                # 预处理（会截断长音频）
                waveform = self._preprocess(waveform)
                # 推理
                return self._predict_tflite(waveform)
                
        except Exception as e:
            logger.error(f"预测失败: {e}", exc_info=True)
            return None
    
    def _predict_sliding_window(self, waveform: np.ndarray) -> Optional[np.ndarray]:
        """
        使用滑动窗口处理长音频
        
        Args:
            waveform: 原始音频波形
            
        Returns:
            聚合后的预测结果 (shape: [num_frames, 521])
        """
        hop_length = self.waveform_length // 2  # 50% 重叠
        num_segments = (len(waveform) - self.waveform_length) // hop_length + 1
        
        all_scores = []
        
        logger.debug(f"长音频分段处理: {len(waveform)} samples, {num_segments} 段")
        
        for i in range(num_segments):
            start = i * hop_length
            end = start + self.waveform_length
            
            if end > len(waveform):
                segment = waveform[start:]
                segment = np.pad(segment, (0, self.waveform_length - len(segment)))
            else:
                segment = waveform[start:end]
            
            # 预处理并推理
            segment = self._preprocess(segment)  # 不强制归一化
            scores = self._predict_tflite(segment)
            
            if scores is not None:
                all_scores.append(scores)
        
        if not all_scores:
            return None
        
        # 取所有段的最大值（保留最显著的特征）
        aggregated = np.max(all_scores, axis=0)
        logger.debug(f"聚合 {len(all_scores)} 个分段结果")
        
        return aggregated
    
    def _preprocess(self, waveform: np.ndarray) -> np.ndarray:
        """
        预处理音频波形
        
        Args:
            waveform: 原始音频
            normalize: 是否进行归一化（可选）
            
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
            # ⚠️ 截断会丢失后面的音频！建议使用 use_sliding_window=True
            waveform = waveform[:self.waveform_length]
            logger.warning(f"音频被截断到 {self.waveform_length} samples，建议使用 use_sliding_window=True")
        
 
        # 1. 消除直流偏置（减去均值）
        waveform -= np.mean(waveform)
        
        # 2. 动态归一化到 [-1, 1]
        # 根据实际信号幅度自适应缩放，避免假设固定格式
        max_val = np.abs(waveform).max()
        if max_val > 0:
            waveform = waveform / max_val
            logger.debug(f"音频归一化: max_val={max_val:.2f}")
        
        # 3. 安全截断（确保严格在 [-1, 1] 之间）
        waveform = np.clip(waveform, -1.0, 1.0)
        
        return waveform
    
    def _predict_tflite(self, waveform: np.ndarray) -> np.ndarray:
        """使用 TFLite 进行预测"""
        # 根据模型期望的形状调整输入张量
        if len(self.expected_input_shape) == 2 and self.expected_input_shape[0] == 1:
            # 模型期望 [1, N] 形状
            input_tensor = np.expand_dims(waveform, axis=0)
        else:
            # 模型期望 [N] 形状
            input_tensor = waveform
        
        # 设置输入
        self.interpreter.set_tensor(
            self.input_details[0]['index'],
            input_tensor
        )
        
        # 推理
        self.interpreter.invoke()
        
        # 获取输出
        scores = self.interpreter.get_tensor(self.output_details[0]['index'])
        
        # 如果输出有batch维度，移除它
        if len(scores.shape) > 2:
            return scores[0]
        return scores
    
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
