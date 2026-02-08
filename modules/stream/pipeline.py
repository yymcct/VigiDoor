"""
流媒体处理管道模块
协调 OSD 渲染和编码推流
"""

import time
import threading
from typing import Optional
from utils.logger import setup_logger

from .frame_queue import FrameQueue
from .osd.renderer import OSDRenderer
from .encoder.base import EncoderBase
from .state import StreamState

logger = setup_logger('stream_pipeline')


class StreamPipeline:
    """
    流媒体处理管道
    
    架构：
    共享内存 → OSD渲染 → 帧队列 → 编码推流
    """
    
    def __init__(
        self,
        osd_renderer: OSDRenderer,
        encoder: EncoderBase,
        encode_queue: FrameQueue
    ):
        """
        初始化处理管道
        
        Args:
            osd_renderer: OSD 渲染器
            encoder: 编码器
            encode_queue: 编码输入队列
        """
        self.osd_renderer = osd_renderer
        self.encoder = encoder
        self.encode_queue = encode_queue
        
        self.encode_thread = None
        self.running = False
        
        # 统计信息
        self.encoded_frame_count = 0
        self.error_count = 0
    
    # TODO 优化线程
    def start(self, state_getter) -> bool:
        """
        启动处理管道
        
        Args:
            state_getter: 获取推流状态的函数
            
        Returns:
            bool: 启动成功返回 True
        """
        if self.running:
            logger.warning("处理管道已在运行")
            return False
        
        try:
            # 1. 启动 OSD 渲染器
            if not self.osd_renderer.start(state_getter):
                logger.error("OSD 渲染器启动失败")
                return False
            
            # 2. 启动编码线程
            self.running = True
            self.state_getter = state_getter
            
            self.encode_thread = threading.Thread(
                target=self._encode_loop,
                name="Encoder-Thread",
                daemon=True
            )
            self.encode_thread.start()
            logger.info("✅ 编码线程已启动")
            
            logger.info("✅ 流媒体处理管道已启动")
            return True
            
        except Exception as e:
            logger.error(f"处理管道启动失败: {e}", exc_info=True)
            self.stop()
            return False
    
    def stop(self):
        """停止处理管道"""
        if not self.running:
            return
        
        logger.info("正在停止流媒体处理管道...")
        self.running = False
        
        # 停止 OSD 渲染器
        self.osd_renderer.stop()
        
        # 等待编码线程退出
        if self.encode_thread:
            self.encode_thread.join(timeout=5)
            if self.encode_thread.is_alive():
                logger.warning("编码线程未在 5 秒内退出")
        
        # 清空队列
        self.encode_queue.clear()
        
        logger.info("✅ 流媒体处理管道已停止")
        logger.info(f"   总编码帧数: {self.encoded_frame_count}")
        logger.info(f"   错误次数: {self.error_count}")
    
    def _encode_loop(self):
        """编码线程主循环"""
        logger.info("⚙️ 编码线程启动")
        
        self.encoded_frame_count = 0
        self.error_count = 0
        max_consecutive_errors = 10
        consecutive_errors = 0
        
        try:
            while self.running:
                state = self.state_getter()
                if state not in [StreamState.STARTING, StreamState.STREAMING]:
                    time.sleep(0.1)
                    continue
                
                # 从队列获取渲染后的帧
                frame_data = self.encode_queue.get(timeout=1.0)
                if frame_data is None:
                    continue
                
                frame, frame_id, timestamp = frame_data
                
                # 编码推流
                try:
                    if self.encoder.encode(frame):
                        self.encoded_frame_count += 1
                        consecutive_errors = 0
                        
                        # 每 10 秒记录一次（假设 30fps）
                        if self.encoded_frame_count % 300 == 0:
                            logger.debug(f"已编码推流 {self.encoded_frame_count} 帧")
                    else:
                        self.error_count += 1
                        consecutive_errors += 1
                        
                        # 首次编码失败时记录详细信息
                        if consecutive_errors == 1:
                            logger.error(
                                f"⚠️ 编码失败（第 {self.encoded_frame_count + 1} 帧）"
                            )
                            logger.error(f"   已成功编码: {self.encoded_frame_count} 帧")
                        
                        if consecutive_errors >= max_consecutive_errors:
                            logger.error(
                                f"❌ 连续 {consecutive_errors} 次编码失败，停止推流"
                            )
                            logger.error(f"   总成功帧数: {self.encoded_frame_count}")
                            logger.error(f"   总失败次数: {self.error_count}")
                            break
                
                except Exception as e:
                    logger.error(f"编码异常: {e}")
                    self.error_count += 1
                    consecutive_errors += 1
                    
                    if consecutive_errors >= max_consecutive_errors:
                        logger.error("连续错误过多，停止推流")
                        break
                    
                    time.sleep(0.1)
            
            logger.info(f"编码循环结束，共编码 {self.encoded_frame_count} 帧")
            
        except Exception as e:
            logger.error(f"编码线程崩溃: {e}", exc_info=True)
        finally:
            logger.info("编码线程退出")
    
    def get_stats(self) -> dict:
        """
        获取管道统计信息
        
        Returns:
            dict: 统计数据
        """
        return {
            'encoded_frames': self.encoded_frame_count,
            'errors': self.error_count,
            'queue_stats': self.encode_queue.get_stats()
        }
