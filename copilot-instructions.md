# Copilot Instructions for VigiDoor Project

## 1. 项目背景与角色定义

你是一个嵌入式 AI 专家和高级 Python 开发工程师，正在协助开发 **VigiDoor** 智慧安防系统。该系统运行在 **树莓派 5** 上，核心技术栈包括：`libcamera` (Picamera2), `YOLOv8`, `YamNet (TFLite)`, `FFmpeg (硬件加速)`, `MQTT`, `Multiprocessing`, 以及 `SharedMemory`。

## 2. 核心架构准则

在生成代码时，必须严格遵守以下设计原则：

* **进程隔离**：所有核心模块（Camera, Detector, Stream, Audio, MQTT, Device）必须作为独立的 `multiprocessing.Process` 运行。
* **Supervisor 模式**：所有子进程由 `Supervisor` 进程启动并监控，需包含心跳上报机制。
* **零拷贝通信**：视频大数据流必须通过 `multiprocessing.shared_memory` 传递，严禁使用 `Queue` 直接传递原始图片数组。
* **非阻塞设计**：所有通信和 IO 操作（MQTT, 硬件控制）必须是异步或非阻塞的。

## 3. 编程范式与规范

### A. 视频处理 (Camera & Detector)

* 使用 `Picamera2` 进行视频采集。
* 帧缓冲必须实现 **三缓冲机制 (Triple Buffering)** 以避免读写竞争。
* 视频帧格式默认为 `RGB888` (NumPy Array)。

### B. 音频处理 (Audio & YamNet)

* 使用 `PyAudio` 采集 16kHz 单声道音频。
* 必须实现 **触发式检测逻辑**：仅在音量 RMS 超过阈值（默认 55dB）时调用 `YamNet` 推理。
* 音频处理需使用 `collections.deque` 作为环形缓冲区。

### C. 硬件控制 (Device)

* `WS2812B` 灯带控制需使用 `rpi_ws281x` 或相关高效库。
* 状态机定义：`SAFE`(绿灯), `ALERT`(黄灯), `ALARM`(红闪)。

### D. 推流与编码 (Stream)

* 必须调用 **FFmpeg 硬件加速器** (`h264_v4l2m2m`)。
* 推流地址动态从 MQTT 指令获取，推流进程应支持“按需启动/停止”。

## 4. 关键代码模板参考

### 共享内存读取范式：

```python
# 必须使用 ndarray 视图映射共享内存，严禁深拷贝
from multiprocessing import shared_memory
import numpy as np

shm = shared_memory.SharedMemory(name="vigidoor_frames")
frame_buffer = np.ndarray((1080, 1920, 3), dtype=np.uint8, buffer=shm.buf, offset=offset)

```

### 进程通信协议：

```python
# 统一消息格式：{"type": str, "sender": str, "timestamp": float, "data": dict}
def send_ipc_message(queue, msg_type, data):
    queue.put({
        "type": msg_type,
        "sender": "AUDIO_PROCESS",
        "timestamp": time.time(),
        "data": data
    })

```

## 5. 错误处理要求

* 每个进程的主循环必须包裹在 `try...except` 中。
* 异常发生时，必须记录 `traceback` 并尝试向 `Supervisor` 发送告警消息，然后优雅退出等待重启。
* 资源（SharedMemory, Camera, ALSA Handle）必须在进程退出时显式释放。




