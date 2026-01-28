"""
OSD 渲染器模块
管理 OSD 渲染线程和帧处理
"""

import time
import threading
from typing import Optional
import numpy as np
from utils.logger import setup_logger
from utils.frame_buffer import SharedFrameBuffer

from .elements import OSDElement
from ..frame_queue import FrameQueue
from ..state import StreamState

logger = setup_logger('osd_renderer')


class OSDRenderer:
    """
    OSD 渲染器
    
    功能：
    - 从共享内存读取原始帧
    - 应用 OSD 元素渲染
    - 输出到帧队列
    """
    
    def __init__(
        self,
        frame_buffer: SharedFrameBuffer,
        output_queue: FrameQueue,
        osd_element: OSDElement,
        frame_ready_event: threading.Event
    ):
        """
        初始化 OSD 渲染器
        
        Args:
            frame_buffer: 共享内存帧缓冲（输入）
            output_queue: 输出帧队列
            osd_element: OSD 渲染元素
            frame_ready_event: 新帧就绪事件
        """
        self.frame_buffer = frame_buffer
        self.output_queue = output_queue
        self.osd_element = osd_element
        self.frame_ready_event = frame_ready_event
        
        self.running = False
        self.thread = None
        
        # 渲染参数（由外部更新）
        self.render_params = {}
        self.params_lock = threading.Lock()
    
    def start(self, state_getter) -> bool:
        """
        启动渲染线程
        
        Args:
            state_getter: 获取推流状态的函数
            
        Returns:
            bool: 启动成功返回 True
        """
        if self.running:
            logger.warning("OSD 渲染器已在运行")
            return False
        
        self.running = True
        self.state_getter = state_getter
        
        self.thread = threading.Thread(
            target=self._render_loop,
            name="OSD-Renderer",
            daemon=True
        )
        self.thread.start()
        
        logger.info("✅ OSD 渲染线程已启动")
        return True
    
    def stop(self):
        """停止渲染线程"""
        if not self.running:
            return
        
        logger.info("正在停止 OSD 渲染线程...")
        self.running = False
        
        # 触发事件让线程快速退出
        self.frame_ready_event.set()
        
        if self.thread:
            self.thread.join(timeout=5)
            if self.thread.is_alive():
                logger.warning("OSD 渲染线程未在 5 秒内退出")
        
        logger.info("✅ OSD 渲染线程已停止")
    
    def update_render_params(self, **params):
        """
        更新渲染参数（线程安全）
        
        Args:
            **params: 渲染参数（如 detections, state 等）
        """
        with self.params_lock:
            self.render_params.update(params)
    
    def _render_loop(self):
        """OSD 渲染主循环（事件驱动）"""
        logger.info("🎨 OSD 渲染循环启动（事件驱动模式）")
        
        last_frame_id = -1
        
        try:
            while self.running:
                state = self.state_getter()
                if state not in [StreamState.STARTING, StreamState.STREAMING]:
                    time.sleep(0.1)
                    continue
                
                # 等待新帧就绪通知（事件驱动）
                if not self.frame_ready_event.wait(timeout=1.0):
                    continue
                
                self.frame_ready_event.clear()
                
                # 读取原始帧
                frame_data = self.frame_buffer.read_frame(copy=True)
                if frame_data is None:
                    continue
                
                frame, frame_id, timestamp = frame_data
                
                # 避免重复处理
                if frame_id <= last_frame_id:
                    continue
                
                last_frame_id = frame_id
                
                # 复制帧（避免修改原始数据）
                frame_osd = frame.copy()
                
                # 应用 OSD 渲染
                with self.params_lock:
                    render_params = self.render_params.copy()
                
                render_params['timestamp'] = timestamp
                
                frame_osd = self.osd_element.render(frame_osd, **render_params)
                
                # 输出到队列
                self.output_queue.put((frame_osd, frame_id, timestamp))
                
        except Exception as e:
            logger.error(f"OSD 渲染循环异常: {e}", exc_info=True)
        finally:
            logger.info("OSD 渲染循环退出")
