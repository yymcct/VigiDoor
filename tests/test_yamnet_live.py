import numpy as np
import tflite_runtime.interpreter as tflite
import sounddevice as sd
import scipy.signal
import csv
import time
from collections import deque

# ─── 配置区 ────────────────────────────────────────────────
MODEL_PATH       = "/home/ubuntu/VigiDoor/models/yamnet.tflite"
LABEL_PATH       = "/home/ubuntu/VigiDoor/models/yamnet_class_map.csv"
SAMPLE_RATE      = 16000          # YamNet 固定要求 16kHz
DURATION         = 0.975          # 推荐 ≈0.975s (YamNet窗口)
CHANNELS         = 2
BLOCK_SIZE       = 16000 // 2     # 每块读0.5秒，缓冲平滑用
CONFIDENCE_TH    = 0.30           # 显示置信度阈值

# ─── 读取类别映射 ──────────────────────────────────────────
with open(LABEL_PATH, encoding="utf-8") as f:
    reader = csv.reader(f)
    next(reader)  # 跳过表头
    class_names = [row[3].strip() for row in reader]   # display_name 列

NUM_CLASSES = len(class_names)
print(f"加载了 {NUM_CLASSES} 个类别（YamNet标准521类）")

# ─── 加载 TFLite 模型 ──────────────────────────────────────
interpreter = tflite.Interpreter(model_path=MODEL_PATH)
interpreter.allocate_tensors()

input_details  = interpreter.get_input_details()
output_details = interpreter.get_output_details()

print("输入形状:", input_details[0]['shape'])
# 预期形状应为 [1, 15600] 或类似（浮点波形）

# ─── 音频缓冲（去直流 + 归一化） ────────────────────────────
audio_buffer = deque(maxlen=int(SAMPLE_RATE * 1.2))  # 多一点点作重叠

def audio_callback(indata, frames, time_info, status):
    if status:
        print(status)
    # 取单声道，float32
    audio = indata[:, 0].astype(np.float32)
    print(f"[DEBUG] 音频回调: frames={frames}, audio shape={audio.shape}, audio range=[{audio.min():.3f}, {audio.max():.3f}]")
    # 去直流
    audio -= np.mean(audio)
    # YamNet期望 [-1.0, 1.0] 范围，不要过度归一化
    # 只在超过范围时才clip
    audio = np.clip(audio, -1.0, 1.0)
    audio_buffer.extend(audio)

# ─── 主循环 ────────────────────────────────────────────────
print("\n启动麦克风实时分类... 按 Ctrl+C 退出\n")

try:
    with sd.InputStream(samplerate=SAMPLE_RATE,
                        channels=CHANNELS,
                        dtype='float32',
                        blocksize=BLOCK_SIZE,
                        device="seedsnoop_plug",
                        callback=audio_callback):

        while True:
            if len(audio_buffer) < int(SAMPLE_RATE * DURATION):
                print(f"[DEBUG] 缓冲区不足: {len(audio_buffer)} / {int(SAMPLE_RATE * DURATION)}")
                time.sleep(0.1)
                continue

            # 取最新一段 ≈0.975秒音频
            waveform = np.array(list(audio_buffer)[-int(SAMPLE_RATE * DURATION):], dtype=np.float32)
            print(f"[DEBUG] 波形: shape={waveform.shape}, range=[{waveform.min():.3f}, {waveform.max():.3f}], mean={waveform.mean():.3f}")

            # 检查是否需要扩展批次维度
            expected_shape = input_details[0]['shape']
            print(f"[DEBUG] 模型期望输入形状: {expected_shape}")
            if len(expected_shape) == 2 and expected_shape[0] == 1:
                waveform = np.expand_dims(waveform, axis=0)
                print(f"[DEBUG] 扩展后波形: shape={waveform.shape}")
            
            interpreter.set_tensor(input_details[0]['index'], waveform)
            interpreter.invoke()

            # 输出 [1, 521] logits
            scores = interpreter.get_tensor(output_details[0]['index'])[0]
            print(f"[DEBUG] Scores: shape={scores.shape}, range=[{scores.min():.3f}, {scores.max():.3f}]")

            # softmax
            exp_scores = np.exp(scores - np.max(scores))
            probs = exp_scores / exp_scores.sum()
            print(f"[DEBUG] Probs: max={probs.max():.3f}, sum={probs.sum():.3f}")

            # 取top3
            top3_idx = np.argsort(probs)[-3:][::-1]
            top3_prob = probs[top3_idx]
            print(f"[DEBUG] Top3: idx={top3_idx}, prob={top3_prob}, threshold={CONFIDENCE_TH}")
            print(f"[DEBUG] Top3类别: {[class_names[idx] for idx in top3_idx]}")

            print(f"\r{time.strftime('%H:%M:%S')} | ", end="")
            output_count = 0
            for i in range(3):
                if top3_prob[i] >= CONFIDENCE_TH:
                    name = class_names[top3_idx[i]]
                    print(f"{name:18} {top3_prob[i]:.3f}  ", end="")
                    output_count += 1
                else:
                    break
            print(f"[输出了{output_count}个类别]  ", end="")
            print("   ", end="", flush=True)

            time.sleep(0.6)  # 控制刷新速度，避免太频繁

except KeyboardInterrupt:
    print("\n\n已停止")

print("程序结束")