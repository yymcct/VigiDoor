"""
流媒体管理进程
"""

import time
import threading
from core.ipc import IPCClient, MessageType
from core.ipc.registry import ProcessName
from utils.logger import setup_logger
from utils.frame_buffer import SharedFrameBuffer

from .state import StateManager, StreamState
from .frame_queue import FrameQueue
from .osd import CompositeOSDElement, TimestampElement, DeviceInfoElement, DetectionBoxElement
from .osd import SkeletonElement, FootTrafficElement
from .osd import OSDDataStore, OSDMessageDispatcher
from .osd.renderer import OSDRenderer
from .encoder import FFmpegEncoder
from .pipeline import StreamPipeline

from core.ipc.message import CommandMessage as IPCCommandMessage, MessageType

logger = setup_logger('stream_manager')


class StreamManagerProcess:
    """
    流媒体管理进程 - 负责视频流的 OSD 渲染和推流
    
    架构：
    ┌────────────────────────────────────┐
    │  StreamManagerProcess (主控)       │
    │  - 接收控制指令                     │
    │  - 管理生命周期                     │
    └────────────────────────────────────┘
              ↓
    ┌────────────────────────────────────┐
    │  StreamPipeline (处理管道)         │
    │    ├─> OSDRenderer (OSD渲染)       │
    │    └─> FFmpegEncoder (编码推流)    │
    └────────────────────────────────────┘
    
    功能：
    1. 从共享内存读取原始帧
    2. OSD 叠加（时间戳、检测框、设备信息）
    3. H.264 编码
    4. RTSP/RTMP 推流
    """
    
    def __init__(self, ipc_client: IPCClient, shared_state, config):
        """
        初始化流媒体管理进程
        
        Args:
            ipc_client: IPC 客户端
            shared_state: 共享状态
            config: 配置字典
        """
        self.ipc = ipc_client
        self.state = shared_state
        self.config = config
        self.running = True
        
        # 推流配置
        self.zlm_server = config['stream']['zlm_server']
        self.stream_key = config['stream']['stream_key'].format(
            device_id=config['device']['id']
        )
        self.stream_url = f"{self.zlm_server}/{self.stream_key}"
        
        # 状态管理
        self.state_manager = StateManager()
        
        # OSD 数据管理
        self.data_store = OSDDataStore(ttl=5.0)
        self.dispatcher = OSDMessageDispatcher(self.data_store)
        
        # 组件（延迟初始化）
        self.frame_buffer = None
        self.osd_renderer = None
        self.encoder = None
        self.pipeline = None
        
        logger.info(f"流媒体管理进程初始化完成")
        logger.info(f"   设备 ID: {config['device']['id']}")
        logger.info(f"   推流地址: {self.stream_url}")
        
        
    
    def run(self):
        """主循环"""
        logger.info("📹 流媒体管理进程启动")
        
        last_heartbeat = time.time()
        
        #TODO 测试代码，启动时自动开始推流，需要重构掉
        stream_msg = IPCCommandMessage(
            cmd_type=MessageType.CMD_START_STREAM,
            target=ProcessName.STREAM_MANAGER,
            cmd_data={}
        )
        self.ipc.send_message(stream_msg)
        try:
            while self.running:
                # 处理消息
                msg = self.ipc.receive(timeout=1.0)
                if msg:
                    self._handle_message(msg)
                
                # 定期发送心跳
                if time.time() - last_heartbeat > 10:
                    self.ipc.send_heartbeat()
                    last_heartbeat = time.time()
                
        except KeyboardInterrupt:
            logger.info("检测到中断信号")
        finally:
            self._stop_stream()
            logger.info("流媒体管理进程退出")
    
    def _handle_message(self, msg):
        """处理 IPC 消息"""
        msg_dict = msg.to_dict()
        msg_type = msg_dict.get('type')
        msg_data = msg_dict.get('data', {})
        
        if msg_type == MessageType.CMD_START_STREAM.value:
            logger.info("📤 收到开始推流指令")
            self._start_stream()
        
        elif msg_type == MessageType.CMD_STOP_STREAM.value:
            logger.info("⏹️  收到停止推流指令")
            self._stop_stream()
        
        elif msg_type == 'detection_result':
            # 委托给 Dispatcher 处理
            self.dispatcher.dispatch(msg_dict)
        
        elif msg_type == MessageType.SHUTDOWN.value:
            logger.info("收到关闭信号")
            self.running = False
    
    def _start_stream(self):
        """启动推流"""
        if not self.state_manager.can_transition_to(StreamState.STARTING):
            logger.warning(
                f"当前状态 {self.state_manager.state.value}，无法启动推流"
            )
            return
        
        try:
            self.state_manager.transition_to(StreamState.STARTING)
            logger.info("开始启动推流...")
            
            # 1. 初始化共享内存
            self._init_shared_memory()
            
            # 2. 初始化组件
            self._init_components()
            
            # 3. 启动处理管道
            if not self.pipeline.start(lambda: self.state_manager.state):
                raise RuntimeError("处理管道启动失败")
            
            # 4. 更新状态
            self.state_manager.transition_to(StreamState.STREAMING)
            self.state['is_streaming'] = True
            logger.info("✅ 推流已启动")
            
        except Exception as e:
            logger.error(f"启动推流失败: {e}", exc_info=True)
            self.state_manager.reset()
            self._cleanup()
    
    def _stop_stream(self):
        """停止推流"""
        if self.state_manager.is_idle():
            return
        
        try:
            logger.info("停止推流...")
            self.state_manager.transition_to(StreamState.STOPPING)
            
            # 停止处理管道
            if self.pipeline:
                self.pipeline.stop()
            
            # 释放编码器
            if self.encoder:
                self.encoder.release()
            
            # 清理资源
            self._cleanup()
            
            # 更新状态
            self.state_manager.transition_to(StreamState.IDLE)
            self.state['is_streaming'] = False
            logger.info("✅ 推流已停止")
            
        except Exception as e:
            logger.error(f"停止推流失败: {e}")
            self.state_manager.reset()
    
    def _init_shared_memory(self):
        """初始化共享内存（读取者模式）"""
        try:
            max_wait = 10
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                try:
                    self.frame_buffer = SharedFrameBuffer(
                        width=self.config['camera']['width'],
                        height=self.config['camera']['height'],
                        name=self.config['camera']['shared_memory_name'],
                        create=False
                    )
                    logger.info("✅ 共享内存连接成功")
                    return
                except FileNotFoundError:
                    logger.warning("等待共享内存创建...")
                    time.sleep(1)
            
            raise RuntimeError("共享内存连接超时")
            
        except Exception as e:
            logger.error(f"共享内存连接失败: {e}")
            raise
    
    def _init_components(self):
        """初始化所有组件"""
        # 1. 创建 OSD 元素
        osd_elements = CompositeOSDElement([
            TimestampElement(position=(20, 40), font_scale=0.8),
            DeviceInfoElement(
                device_id=self.config['device']['id'],
                position=None  # 自动定位到左下角
            ),
            DetectionBoxElement(box_thickness=2, text_font_scale=0.5),
            SkeletonElement(
                line_thickness=2,
                keypoint_radius=3,
                confidence_threshold=0.5
            ),
            FootTrafficElement(
                position=None,  # 自动定位到右上角
                font_scale=0.8
            )
        ])
        
        # 2. 创建帧队列
        encode_queue = FrameQueue(maxsize=5, name="EncodeQueue")
        
        # 3. 创建 OSD 渲染器
        self.osd_renderer = OSDRenderer(
            frame_buffer=self.frame_buffer,
            output_queue=encode_queue,
            osd_element=osd_elements,
            data_store=self.data_store
        )
        logger.info("✅ OSD 渲染器初始化完成")
        
        # 4. 创建编码器
        self.encoder = FFmpegEncoder(
            width=self.config['camera']['width'],
            height=self.config['camera']['height'],
            fps=self.config['stream']['fps'],
            bitrate=self.config['stream']['bitrate']
        )
        
        if not self.encoder.initialize(self.stream_url):
            raise RuntimeError("编码器初始化失败")
        
        logger.info("✅ 编码器初始化完成")
        
        # 5. 创建处理管道
        self.pipeline = StreamPipeline(
            osd_renderer=self.osd_renderer,
            encoder=self.encoder,
            encode_queue=encode_queue
        )
        logger.info("✅ 处理管道初始化完成")
    
    def _cleanup(self):
        """清理资源"""
        logger.info("正在清理资源...")
        
        # 关闭共享内存
        if self.frame_buffer:
            try:
                self.frame_buffer.close()
                self.frame_buffer = None
            except Exception as e:
                logger.error(f"关闭共享内存失败: {e}")
        
        logger.info("✅ 资源清理完成")
