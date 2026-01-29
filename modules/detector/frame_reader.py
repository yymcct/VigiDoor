"""
帧读取器
封装共享内存读取逻辑
"""

import time
from typing import Optional, Tuple
import numpy as np
from utils.logger import setup_logger
from utils.frame_buffer import SharedFrameBuffer

logger = setup_logger('frame_reader')


class FrameReader:
    """
    帧读取器 - 从共享内存读取相机帧
    
    功能：
    1. 连接到共享内存
    2. 读取最新帧数据
    3. 跟踪已处理的帧ID（避免重复）
    """
    
    def __init__(self, config: dict):
        """
        Args:
            config: 相机配置（包含width, height, shared_memory_name）
        """
        self.config = config
        self.frame_buffer = None
        self.last_frame_id = -1
        
        logger.info("帧读取器初始化")
    
    def connect(self, max_wait: float = 10.0) -> bool:
        """
        连接到共享内存
        
        Args:
            max_wait: 最大等待时间（秒）
        
        Returns:
            bool: 是否连接成功
        """
        try:
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                try:
                    self.frame_buffer = SharedFrameBuffer(
                        width=self.config['width'],
                        height=self.config['height'],
                        name=self.config['shared_memory_name'],
                        create=False  # 读取者模式
                    )
                    logger.info("✅ 共享内存连接成功")
                    return True
                    
                except FileNotFoundError:
                    logger.warning("等待共享内存创建...")
                    time.sleep(1)
            
            logger.error(f"共享内存连接超时（{max_wait}秒）")
            return False
            
        except Exception as e:
            logger.error(f"共享内存连接失败: {e}")
            return False
    
    def read_new_frame(self, copy: bool = True) -> Optional[Tuple[np.ndarray, int, float]]:
        """
        读取新帧（跳过已处理的帧）
        
        Args:
            copy: 是否复制帧数据（True更安全，False更快）
        
        Returns:
            (frame, frame_id, timestamp) 或 None（无新帧）
        """
        if self.frame_buffer is None:
            logger.warning("帧缓冲未连接")
            return None
        
        try:
            frame_data = self.frame_buffer.read_frame(copy=copy)
            
            if frame_data is None:
                return None
            
            frame, frame_id, timestamp = frame_data
            
            # 检查是否是新帧
            if frame_id <= self.last_frame_id:
                return None
            
            # 更新最后处理的帧ID
            self.last_frame_id = frame_id
            
            return frame, frame_id, timestamp
            
        except Exception as e:
            logger.error(f"读取帧失败: {e}")
            return None
    
    def read_latest_frame(self, copy: bool = True) -> Optional[Tuple[np.ndarray, int, float]]:
        """
        读取最新帧（不检查是否重复）
        
        Args:
            copy: 是否复制帧数据
        
        Returns:
            (frame, frame_id, timestamp) 或 None
        """
        if self.frame_buffer is None:
            return None
        
        try:
            return self.frame_buffer.read_frame(copy=copy)
        except Exception as e:
            logger.error(f"读取帧失败: {e}")
            return None
    
    def close(self):
        """关闭共享内存连接"""
        try:
            if self.frame_buffer:
                self.frame_buffer.close()
                logger.info("共享内存连接已关闭")
        except Exception as e:
            logger.error(f"关闭共享内存失败: {e}")
