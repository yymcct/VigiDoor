"""
IPC 通信封装模块
负责所有与其他进程的通信
"""

import time
from core.ipc import IPCClient, MessageType
from core.ipc.message import FrameReadyMessage
from core.ipc.registry import ProcessName
from utils.logger import setup_logger

logger = setup_logger('camera_communicator')


class CameraCommunicator:
    """
    摄像头进程通信器
    
    封装所有 IPC 通信逻辑：
    - 发送帧就绪通知
    - 发送心跳
    - 检查关闭信号
    """
    
    def __init__(self, ipc_client: IPCClient, width: int, height: int):
        """
        初始化通信器
        
        Args:
            ipc_client: IPC 客户端实例
            width: 图像宽度
            height: 图像高度
        """
        self.ipc = ipc_client
        self.width = width
        self.height = height
        self.last_heartbeat = time.time()
        self.heartbeat_interval = 1.0  # 心跳间隔（秒）
    
    def notify_frame_ready(self, frame_id: int, timestamp: float):
        """
        通知新帧就绪
        
        Args:
            frame_id: 帧序号
            timestamp: 时间戳
        """
        try:
            msg = FrameReadyMessage(
                frame_id=frame_id,
                timestamp=timestamp,
                width=self.width,
                height=self.height,
                target=ProcessName.STREAM_MANAGER
            )
            self.ipc.send_message(msg)
        except Exception as e:
            logger.error(f"发送帧就绪消息失败: {e}")
    
    def send_heartbeat(self, fps: int, frame_count: int) -> bool:
        """
        发送心跳（带性能数据）
        
        Args:
            fps: 当前帧率
            frame_count: 总帧数
            
        Returns:
            bool: 是否已发送心跳
        """
        now = time.time()
        
        if now - self.last_heartbeat >= self.heartbeat_interval:
            try:
                # TODO 重构
                self.ipc.send(
                    msg_type=MessageType.HEARTBEAT,
                    target=ProcessName.SUPERVISOR,
                    data={
                        'fps': fps,
                        'frame_count': frame_count
                    }
                )
                self.last_heartbeat = now
                return True
            except Exception as e:
                logger.error(f"发送心跳失败: {e}")
        
        return False
    
    def check_shutdown_signal(self, timeout: float = 0.001) -> bool:
        """
        检查是否收到关闭信号
        
        Args:
            timeout: 接收超时时间（秒）
            
        Returns:
            bool: 如果收到关闭信号返回 True
        """
        try:
            msg = self.ipc.receive(timeout=timeout)
            if msg:
                msg_dict = msg.to_dict() if hasattr(msg, 'to_dict') else msg
                if msg_dict.get('type') in ['shutdown', MessageType.SHUTDOWN.value]:
                    logger.info("收到关闭信号")
                    return True
        except Exception as e:
            logger.debug(f"检查关闭信号异常: {e}")
        
        return False
