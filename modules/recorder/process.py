"""
RecorderProcess — 本地分段录像进程

职责：
  1. 连接 SharedFrameBuffer（Supervisor 创建，不持有所有权）
  2. 创建 SegmentRecorder（驱动 FFmpeg 分段录像）和 SegmentIndexer（DB 索引）
  3. 处理 IPC 消息：CMD_TAG_RECORDING → 给当前片段打标
  4. 启动时调度每日存储清理（按 retention_days 删除超期文件和 DB 记录）

进程入口由 modules/supervisor/process_registry.py 中的
run_recorder 函数调用。
"""

import os
import time
import threading
import logging

from core.process_context import ProcessContext
from core.ipc.message import MessageType
from db.writer_helper import DBWriterHelper
from utils.frame_buffer import SharedFrameBuffer

from .segment_indexer import SegmentIndexer
from .segment_recorder import SegmentRecorder

logger = logging.getLogger(__name__)


class RecorderProcess:
    """本地持续分段录像进程"""

    def __init__(self, ctx: ProcessContext):
        self._ipc = ctx.ipc
        self._config = ctx.config
        self._running = True

        rec_cfg = self._config.recording
        self._output_dir: str = rec_cfg.dir
        self._segment_duration: int = int(rec_cfg.segment_duration)
        self._retention_days: int = int(rec_cfg.retention_days)
        self._bitrate: str = rec_cfg.bitrate
        self._fps: int = int(rec_cfg.fps)
        self._enabled: bool = bool(rec_cfg.enabled)

        cam = self._config.camera
        self._width: int = cam.width
        self._height: int = cam.height
        self._shared_memory_name: str = cam.shared_memory_name

        self._frame_buffer: SharedFrameBuffer = None
        self._db_writer: DBWriterHelper = DBWriterHelper(self._ipc)
        self._indexer: SegmentIndexer = SegmentIndexer(self._db_writer)
        self._recorder: SegmentRecorder = None

        logger.info("📼 RecorderProcess 初始化完成")
        logger.info(f"   输出目录: {self._output_dir}")
        logger.info(f"   分段时长: {self._segment_duration}s  保留: {self._retention_days}天")
        logger.info(f"   码率: {self._bitrate}  帧率: {self._fps} FPS")

    # ------------------------------------------------------------------
    # 进程入口
    # ------------------------------------------------------------------

    def run(self) -> None:
        if not self._enabled:
            logger.info("录像功能已禁用（recording.enabled=false），进程退出")
            return

        logger.info("🚀 RecorderProcess 启动")

        try:
            self._init_shared_memory()
            self._ensure_output_dir()
            self._start_ipc_listener()
            self._schedule_cleanup()
            self._run_recording()
        except KeyboardInterrupt:
            logger.info("检测到中断信号")
        except Exception as e:
            logger.error(f"RecorderProcess 异常: {e}", exc_info=True)
        finally:
            self._cleanup()
            logger.info("RecorderProcess 已退出")

    # ------------------------------------------------------------------
    # 初始化
    # ------------------------------------------------------------------

    def _init_shared_memory(self) -> None:
        """连接到由 Supervisor 创建的共享内存帧缓冲（不持有所有权）"""
        max_wait = 15
        start = time.time()
        while time.time() - start < max_wait:
            try:
                self._frame_buffer = SharedFrameBuffer(
                    width=self._width,
                    height=self._height,
                    name=self._shared_memory_name,
                    create=False,
                )
                logger.info("✅ 共享内存帧缓冲连接成功")
                return
            except FileNotFoundError:
                logger.warning("等待 Supervisor 创建共享内存...")
                time.sleep(1)
            except Exception as e:
                logger.error(f"共享内存连接失败: {e}")
                raise
        raise RuntimeError(f"共享内存连接超时（{max_wait}s），Supervisor 可能未就绪")

    def _ensure_output_dir(self) -> None:
        os.makedirs(self._output_dir, exist_ok=True)
        logger.info(f"录像输出目录已就绪: {self._output_dir}")

    # ------------------------------------------------------------------
    # 录像主循环
    # ------------------------------------------------------------------

    def _run_recording(self) -> None:
        self._recorder = SegmentRecorder(
            frame_buffer=self._frame_buffer,
            width=self._width,
            height=self._height,
            fps=self._fps,
            output_dir=self._output_dir,
            segment_duration=self._segment_duration,
            bitrate=self._bitrate,
            on_segment_opened=self._indexer.on_segment_opened,
        )
        self._recorder.start()
        # 阻塞直到 stop() 被调用
        self._recorder.run_capture_loop()

    # ------------------------------------------------------------------
    # IPC 消息处理（独立线程）
    # ------------------------------------------------------------------

    def _start_ipc_listener(self) -> None:
        t = threading.Thread(
            target=self._ipc_loop,
            name="RecorderIPC",
            daemon=True,
        )
        t.start()
        logger.info("🧵 RecorderProcess IPC 监听线程已启动")

    def _ipc_loop(self) -> None:
        while self._running:
            try:
                msg = self._ipc.receive(timeout=1)
                if msg is None:
                    continue
                self._handle_message(msg)
            except Exception as e:
                if self._running:
                    logger.debug(f"IPC 接收超时或错误: {e}")

    def _handle_message(self, msg) -> None:
        mtype = msg.msg_type
        data = msg.data or {}

        if mtype == MessageType.CMD_TAG_RECORDING:
            alarm_level = data.get("alarm_level", "alarm")
            self._indexer.tag_current_clip(alarm_level)

        elif mtype == MessageType.SHUTDOWN:
            logger.info("收到 SHUTDOWN 指令")
            self._running = False
            if self._recorder:
                self._recorder.stop()

        else:
            logger.debug(f"RecorderProcess 忽略消息: {mtype}")

    # ------------------------------------------------------------------
    # 存储清理（每日）
    # ------------------------------------------------------------------

    def _schedule_cleanup(self) -> None:
        if self._retention_days <= 0:
            logger.info("retention_days <= 0，跳过自动清理调度")
            return

        def cleanup_loop():
            # 启动后等待一小时再第一次执行，避免启动期间 IO 竞争
            time.sleep(3600)
            while self._running:
                self._run_cleanup()
                time.sleep(86400)

        t = threading.Thread(target=cleanup_loop, name="RecorderCleanup", daemon=True)
        t.start()
        logger.info(f"🗂️ 录像自动清理已调度（保留 {self._retention_days} 天）")

    def _run_cleanup(self) -> None:
        """删除超过 retention_days 的录像文件"""
        import glob
        from pathlib import Path

        cutoff = time.time() - self._retention_days * 86400
        pattern = os.path.join(self._output_dir, "*.ts")
        removed = 0

        for fpath in glob.glob(pattern):
            try:
                mtime = os.path.getmtime(fpath)
                if mtime < cutoff:
                    os.remove(fpath)
                    removed += 1
                    logger.debug(f"已删除过期录像: {os.path.basename(fpath)}")
            except OSError as e:
                logger.warning(f"删除录像文件失败: {fpath} - {e}")

        if removed:
            logger.info(f"🗑️ 已清理 {removed} 个过期录像文件")

    # ------------------------------------------------------------------
    # 资源清理
    # ------------------------------------------------------------------

    def _cleanup(self) -> None:
        self._running = False

        if self._recorder:
            self._recorder.stop()

        self._indexer.on_recording_stopped()

        if self._frame_buffer:
            try:
                self._frame_buffer.close()
            except Exception as e:
                logger.error(f"关闭共享内存失败: {e}")

        logger.info("✅ RecorderProcess 资源已清理")
