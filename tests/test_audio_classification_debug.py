"""
音频分类调试工具
用于测试 YamNet 分类准确性
"""

import sys
import warnings
import numpy as np
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.audio.models import YamNetLoader, EventClassifier
from utils.logger import setup_logger

logger = setup_logger('audio_debug', level='DEBUG')

# Suppress benign NumPy getlimits warnings on some platforms.
warnings.filterwarnings(
    "ignore",
    message="The value of the smallest subnormal.*",
    category=UserWarning,
    module="numpy\\.core\\.getlimits",
)


def test_audio_classification(audio_path: str = None):
    """测试音频分类"""
    
    # 1. 加载模型
    print("=" * 60)
    print("🔧 加载 YamNet 模型...")
    print("=" * 60)
    
    yamnet = YamNetLoader('models/yamnet.tflite')
    if not yamnet.load():
        print("❌ 模型加载失败")
        return
    
    # 2. 初始化分类器
    classifier = EventClassifier(
        class_names_path='models/yamnet_class_map.csv',
        confidence_threshold=0.3,
        enable_dog_bark=True
    )
    
    # 3. 准备测试音频
    if audio_path:
        print(f"\n📂 加载音频文件: {audio_path}")
        import soundfile as sf
        audio_data, sr = sf.read(audio_path, dtype='float32')
        
        # 如果是双声道，转单声道
        if audio_data.ndim == 2:
            audio_data = np.mean(audio_data, axis=1)
            print(f"   转换双声道 -> 单声道")
        
        # 重采样到 16kHz（如果需要）
        if sr != 16000:
            print(f"   需要重采样: {sr}Hz -> 16000Hz")
            try:
                import librosa
            except ImportError:
                print(f"   ⚠️  未安装 librosa，请先安装: pip install librosa")
                return
            audio_data = librosa.resample(audio_data, orig_sr=sr, target_sr=16000)
            audio_data = audio_data.astype(np.float32, copy=False)
            sr = 16000
            print("   ✅ 已重采样到 16000Hz")
            
        print(f"   采样率: {sr}Hz")
        print(f"   长度: {len(audio_data)} samples ({len(audio_data)/sr:.2f}秒)")
        print(f"   范围: [{audio_data.min():.3f}, {audio_data.max():.3f}]")
    else:
        # 生成测试音频（1秒，正弦波）
        print("\n🎵 生成测试音频（1秒正弦波 @ 440Hz）")
        sr = 16000
        duration = 1.0
        freq = 440  # A4 音符
        t = np.linspace(0, duration, int(sr * duration))
        audio_data = 0.5 * np.sin(2 * np.pi * freq * t).astype(np.float32)
    
    # 4. YamNet 推理
    print("\n" + "=" * 60)
    print("🔍 YamNet 推理...")
    print("=" * 60)
    
    # 🔥 使用滑动窗口处理完整音频（重要！）
    scores = yamnet.predict(audio_data, use_sliding_window=True)
    if scores is None:
        print("❌ 推理失败")
        return
    
    print(f"✅ 推理成功")
    print(f"   输出 shape: {scores.shape}")
    print(f"   帧数: {scores.shape[0]}")
    
    # 5. 获取 Top-10 预测
    top_predictions = yamnet.get_top_predictions(scores, top_k=10)
    
    print("\n" + "=" * 60)
    print("🏆 Top-10 分类结果")
    print("=" * 60)
    print(f"{'排名':<6} {'类别ID':<8} {'置信度':<10} {'类别名称'}")
    print("-" * 60)
    
    for i, (class_id, confidence) in enumerate(top_predictions, 1):
        class_name = classifier.class_names.get(class_id, "未知") if classifier.class_names else "N/A"
        print(f"{i:<6} {class_id:<8} {confidence:<10.4f} {class_name}")
    
    # 6. 异常事件检测
    print("\n" + "=" * 60)
    print("🚨 异常事件检测")
    print("=" * 60)
    
    event_result = classifier.classify(top_predictions)
    
    if event_result:
        event_type, confidence, class_id = event_result
        event_name = classifier.get_event_description(event_type)
        class_name = classifier.class_names.get(class_id, "未知") if classifier.class_names else "N/A"
        
        print(f"✅ 检测到异常事件！")
        print(f"   事件类型: {event_name} ({event_type.value})")
        print(f"   置信度: {confidence:.4f}")
        print(f"   类别 ID: {class_id}")
        print(f"   类别名称: {class_name}")
    else:
        print("ℹ️  未检测到异常事件（正常声音）")
    
    # 7. 显示监控的类别
    print("\n" + "=" * 60)
    print("📋 当前监控的类别")
    print("=" * 60)
    
    for event_type, class_ids in classifier.EVENT_MAPPING.items():
        if event_type.value == 'dog_bark' and not classifier.enable_dog_bark:
            continue
        
        event_name = classifier.get_event_description(event_type)
        print(f"\n{event_name} ({event_type.value}):")
        for class_id in class_ids:
            class_name = classifier.class_names.get(class_id, "未知") if classifier.class_names else "N/A"
            print(f"  - ID {class_id}: {class_name}")


if __name__ == '__main__':

    #audio_file ='/home/ubuntu/VigiDoor/tests/beldesign-slow-motion-glass-shatter.wav'
    audio_file = '/home/ubuntu/VigiDoor/logs/audio_debug/20260206_150622_011.wav'
    test_audio_classification(audio_file)
