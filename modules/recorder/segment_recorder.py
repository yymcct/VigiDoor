"""
SegmentRecorder — FFmpeg 分段录像驱动

职责：
  1. 从 SharedFrameBuffer 持续读取原始 BGR24 帧
  2. 用 cv2.putText 叠加时间戳
  3. 通过 stdin pipe 将帧送入 FFmpeg
  4. FFmpeg 使用 `-f segment` 每 60 秒自动切一个新 MP4 文件
  5. 解析 FFmpeg stderr `Opening '...' for writing` 行，回调 on_segment_opened

FFmpeg 命令示意：
  ffmpeg -f rawvideo -pix_fmt bgr24 -s WxH -r FPS -i pipe:0
         -c:v libx264 -preset ultrafast -tune stillimage -crf 28
         -f segment -segment_time 60 -reset_timestamps 1
         -strftime 1 "<dir>/%Y%m%d_%H%M%S.mp4"
"""

import os
import re
import subprocess
import threading
import time
import logging
from datetime import datetime
from typing import Callable, Optional

import cv2
import numpy as np

from utils.frame_buffer import SharedFrameBuffer

logger = logging.getLogger(__name__)

# FFmpeg stderr 解析：匹配 "Opening '...' for writing"
_SEGMENT_OPEN_RE = re.compile(r"Opening '(.+?)' for writing")


class SegmentRecorder:
    """持续分段录像器"""

    def __init__(
        self,
        frame_buffer: SharedFrameBuffer,
        width: int,
        height: int,
        fps: int,
        output_dir: str,
        segment_duration: int,
        bitrate: str,
        on_segment_opened: Callable[[str, float], None],
    ):
        """
        Args:
            frame_buffer:       共享内存帧缓冲（只读）
            width/height:       帧分辨率
            fps:                录像帧率
            output_dir:         输出目录（需预先存在）
            segment_duration:   每段时长（秒）
            bitrate:            视频码率，如 "800k"
            on_segment_opened:  新片段开始时的回调 (file_path, start_time)
        """
        self._frame_buffer = frame_buffer
        self._width = width
        self._height = height
        self._fps = fps
        self._output_dir = output_dir
        self._segment_duration = segment_duration
        self._bitrate = bitrate
        self._on_segment_opened = on_segment_opened

        self._proc: Optional[subprocess.Popen] = None
        self._stderr_thread: Optional[threading.Thread] = None
        self._running = False

        # 帧率控制
        self._frame_interval = 1.0 / fps
        self._last_frame_id: Optional[int] = None  # 用于去重，避免重复写同一帧

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    def start(self) -> None:
        """启动 FFmpeg 子进程和 stderr 监听线程"""
        if self._running:
            return
        self._running = True
        self._proc = self._launch_ffmpeg()
        self._stderr_thread = threading.Thread(
            target=self._read_stderr,
            name="RecorderStderr",
            daemon=True,
        )
        self._stderr_thread.start()
        logger.info("🎬 SegmentRecorder 已启动")

    def run_capture_loop(self) -> None:
        """
        主线程调用：持续从共享内存读帧并写入 FFmpeg stdin。
        阻塞直到 stop() 被调用，或 FFmpeg 异常退出。
        """
        logger.info("🎥 录像帧捕获循环开始")
        consecutive_errors = 0

        while self._running:
            loop_start = time.monotonic()
            try:
                frame_data = self._frame_buffer.read_frame(copy=True)
                if frame_data is None:
                    time.sleep(0.05)
                    continue

                frame, meta = frame_data
                frame_id = meta.get("frame_id")

                # 去重：跳过同一帧
                if frame_id is not None and frame_id == self._last_frame_id:
                    elapsed = time.monotonic() - loop_start
                    sleep_time = self._frame_interval - elapsed
                    if sleep_time > 0:
                        time.sleep(sleep_time)
                    continue
                self._last_frame_id = frame_id

                # 叠加时间戳（只需时间戳，不含检测框等 OSD）
                annotated = self._draw_timestamp(frame)

                # 转为 BGR24 写入 pipe（frame_buffer 存 RGB，需转换）
                bgr = cv2.cvtColor(annotated, cv2.COLOR_RGB2BGR)

                if self._proc and self._proc.stdin:
                    self._proc.stdin.write(bgr.tobytes())
                    consecutive_errors = 0

            except BrokenPipeError:
                logger.error("FFmpeg stdin pipe 已断开，停止录像")
                break
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"录像帧写入错误 ({consecutive_errors}): {e}")
                if consecutive_errors > 10:
                    logger.error("连续错误超过阈值，停止录像")
                    break
                time.sleep(0.1)
                continue

            # 帧率限速
            elapsed = time.monotonic() - loop_start
            sleep_time = self._frame_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

        logger.info("录像帧捕获循环已退出")

    def stop(self) -> None:
        """优雅停止录像器"""
        if not self._running:
            return
        logger.info("正在停止 SegmentRecorder...")
        self._running = False

        if self._proc:
            try:
                if self._proc.stdin:
                    self._proc.stdin.close()
                self._proc.wait(timeout=10)
            except Exception as e:
                logger.warning(f"等待 FFmpeg 退出超时，强制终止: {e}")
                self._proc.kill()
            self._proc = None

        logger.info("✅ SegmentRecorder 已停止")

    # ------------------------------------------------------------------
    # 内部实现
    # ------------------------------------------------------------------

    def _launch_ffmpeg(self) -> subprocess.Popen:
        """构建并启动 FFmpeg 进程"""
        output_pattern = os.path.join(self._output_dir, "%Y%m%d_%H%M%S.mp4")

        cmd = [
            "ffmpeg", "-y",
            # 输入：raw video from stdin
            "-f", "rawvideo",
            "-pix_fmt", "bgr24",
            "-s", f"{self._width}x{self._height}",
            "-r", str(self._fps),
            "-i", "pipe:0",
            # 编码
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "28",
            "-b:v", self._bitrate,
            "-pix_fmt", "yuv420p",
            # 分段输出
            "-f", "segment",
            "-segment_time", str(self._segment_duration),
            "-reset_timestamps", "1",
            "-segment_format", "mp4",
            "-strftime", "1",
            output_pattern,
        ]

        logger.info(f"启动 FFmpeg 录像: {' '.join(cmd)}")

        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        return proc

    def _read_stderr(self) -> None:
        """后台线程：读取 FFmpeg stderr，捕获分段文件名"""
        try:
            for raw_line in self._proc.stderr:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line:
                    continue

                # 捕获新分段文件打开事件
                m = _SEGMENT_OPEN_RE.search(line)
                if m:
                    file_path = m.group(1)
                    open_time = time.time()
                    try:
                        self._on_segment_opened(file_path, open_time)
                    except Exception as cb_err:
                        logger.error(f"on_segment_opened 回调异常: {cb_err}")
                    continue

                # 过滤 FFmpeg 常规日志，仅记录 warning/error
                lower = line.lower()
                if any(kw in lower for kw in ("error", "warning", "invalid", "failed")):
                    logger.warning(f"[ffmpeg] {line}")
                else:
                    logger.debug(f"[ffmpeg] {line}")
        except Exception as e:
            if self._running:
                logger.error(f"读取 FFmpeg stderr 异常: {e}")

    @staticmethod
    def _draw_timestamp(frame: np.ndarray) -> np.ndarray:
        """在帧左上角叠加当前时间戳（原地修改副本）"""
        out = frame.copy()
        ts_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(
            out,
            ts_text,
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        return out
