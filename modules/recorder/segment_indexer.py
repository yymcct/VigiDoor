"""
SegmentIndexer — 录像片段 DB 索引管理

维护当前正在录制的片段状态，当 FFmpeg 打开新文件时：
  1. finalize 上一个片段（更新结束时间、文件大小）
  2. 为新片段调用 write_recording_start

还暴露 tag_current_clip(alarm_level) 供 RecorderProcess 在收到
CMD_TAG_RECORDING 时调用，以给当前片段打上 alert/alarm 标记。
"""

import os
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class SegmentIndexer:
    """录像片段 SQLite 索引管理器"""

    def __init__(self, db_writer):
        """
        Args:
            db_writer: DBWriterHelper 实例（来自子进程 IPC）
        """
        self._writer = db_writer
        self._current_file: Optional[str] = None
        self._current_start: Optional[float] = None

    # ------------------------------------------------------------------
    # 由 SegmentRecorder 的 on_segment_opened 回调触发
    # ------------------------------------------------------------------

    def on_segment_opened(self, file_path: str, open_time: float) -> None:
        """
        FFmpeg 开始写新片段时调用。

        Args:
            file_path: 新片段的文件路径
            open_time: 片段开始时间（Unix timestamp）
        """
        # 先 finalize 上一段
        if self._current_file:
            self._finalize(end_time=open_time)

        # 记录新段
        self._current_file = file_path
        self._current_start = open_time
        self._writer.write_recording_start(file_path, open_time)
        logger.info(f"📼 新录像片段: {os.path.basename(file_path)}")

    def on_recording_stopped(self) -> None:
        """录像停止时 finalize 最后一个片段"""
        if self._current_file:
            self._finalize(end_time=time.time())
            self._current_file = None
            self._current_start = None

    # ------------------------------------------------------------------
    # 报警打标（由 IPC CMD_TAG_RECORDING 触发）
    # ------------------------------------------------------------------

    def tag_current_clip(self, alarm_level: str) -> None:
        """
        给当前正在录制的片段打报警标签。

        Args:
            alarm_level: 'alert' 或 'alarm'
        """
        if not self._current_file:
            logger.warning("tag_current_clip: 当前无活跃录像片段，忽略")
            return
        self._writer.tag_clip_alarm(self._current_file, alarm_level)
        logger.info(f"🚨 录像片段已打标 [{alarm_level}]: {os.path.basename(self._current_file)}")

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    def _finalize(self, end_time: float) -> None:
        """finalize 当前片段"""
        file_path = self._current_file
        try:
            size = os.path.getsize(file_path) if os.path.exists(file_path) else None
        except OSError:
            size = None
        self._writer.finalize_recording_clip(file_path, end_time, size)
        logger.debug(f"片段已 finalize: {os.path.basename(file_path)}")
