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
from .data_store import OSDDataStore
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
        data_store: OSDDataStore
    ):
        """
        初始化 OSD 渲染器
        
        Args:
            frame_buffer: 共享内存帧缓冲（输入）
            output_queue: 输出帧队列
            osd_element: OSD 渲染元素
            data_store: OSD数据仓库（提供渲染数据）
        """
        self.frame_buffer = frame_buffer
        self.output_queue = output_queue
        self.osd_element = osd_element
        self.data_store = data_store
        
        self.running = False
        self.thread = None
    
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
        
        if self.thread:
            self.thread.join(timeout=5)
            if self.thread.is_alive():
                logger.warning("OSD 渲染线程未在 5 秒内退出")
        
        logger.info("✅ OSD 渲染线程已停止")
    
    def _render_loop(self):
        """主渲染循环（轮询模式）"""
        logger.info("🎨 OSD 渲染循环启动（轮询模式）")
        
        last_frame_id = -1
        check_interval = 0.033  # ~30fps的轮询间隔
        
        try:
            while self.running:
                state = self.state_getter()
                if state not in [StreamState.STARTING, StreamState.STREAMING]:
                    time.sleep(0.1)
                    continue
                
                # 直接读取共享内存（轮询）
                frame_data = self.frame_buffer.read_frame(copy=True)
                if frame_data is None:
                    time.sleep(check_interval)
                    continue
                
                frame, frame_id, timestamp = frame_data
                
                # 新帧检测（避免重复处理）
                if frame_id <= last_frame_id:
                    time.sleep(check_interval)
                    continue
                
                last_frame_id = frame_id
                
                # 复制帧（避免修改原始数据）
                frame_osd = frame.copy()
                
                # 从 DataStore 获取渲染数据（自动过滤过期数据）
                render_data = self.data_store.get_render_data()
                render_data['timestamp'] = timestamp
                
                # 应用 OSD 渲染
                frame_osd = self.osd_element.render(frame_osd, **render_data)
                
                # 输出到队列
                self.output_queue.put((frame_osd, frame_id, timestamp))
                
        except Exception as e:
            logger.error(f"OSD 渲染循环异常: {e}", exc_info=True)
        finally:
            logger.info("OSD 渲染循环退出")