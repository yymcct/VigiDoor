#!/usr/bin/env python3
"""
VigiDoor Supervisor - 智慧安防门主进程管理器

这是一个轻量级协调器，负责组装和协调各个管理器组件：
- ProcessManager: 进程生命周期管理
- HealthMonitor: 健康监控和上报
- SharedStateManager: 共享状态管理
- DBManager: 数据库管理
- MessageRouter: 消息路由处理
"""

import multiprocessing as mp
import signal
import time
import threading
import os
import sys
import queue

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.logger import setup_logger
from utils.frame_buffer import SharedFrameBuffer
from core.ipc import MessageBus
from core.ipc.message import MessageType, IPCMessage, CommandMessage
from core.ipc.registry import ProcessName

from modules.supervisor import (
    DBManager,
    ProcessManager,
    HealthMonitor,
    SharedStateManager,
    create_process_configs,
)
from modules.supervisor.handlers import SupervisorHandlerContext
from modules.supervisor.message_router import MessageRouter

logger = setup_logger('supervisor')


class ProcessSupervisor:
    """
    进程监督者 - 轻量级系统协调中心
    
    职责：仅负责组装和协调各个管理器组件
    - 初始化配置和消息总线
    - 创建各个管理器实例
    - 协调启动和关闭流程
    - 处理消息路由
    """
    
    def __init__(self, config_path: str = "./config.yaml"):
        # 1. 先确保数据库已初始化
        self._ensure_db_initialized()
        
        # 2. 初始化 ConfigManager（内部会从 DB 读取配置）
        from utils.config import ConfigManager
        ConfigManager.initialize(config_path)
        self.config_manager = ConfigManager.get_instance()
        self.config_path = config_path
        
        # 创建消息总线
        self.message_bus = MessageBus(max_queue_size=1000)
        
        # 从数据库加载初始布撤防状态
        initial_armed = self._load_initial_arm_status()

        # 创建共享状态管理器
        self.state_manager = SharedStateManager(self.config_manager, initial_armed=initial_armed)
        
        # 创建进程配置
        process_configs = create_process_configs(self.config_manager)
        
        # 创建进程管理器
        self.process_manager = ProcessManager(
            message_bus=self.message_bus,
            state_manager=self.state_manager,
            process_configs=process_configs,
            config_path=self.config_path,
            logger=logger
        )
        
        # 创建健康监控器
        self.health_monitor = HealthMonitor(
            process_manager=self.process_manager,
            ipc_client=self.message_bus.get_client(ProcessName.SUPERVISOR),
            state_manager=self.state_manager,
            config_manager=self.config_manager,
            logger=logger
        )
        
        # 创建消息路由器
        from db.writer_helper import DBWriterHelper
        message_handler_ctx = SupervisorHandlerContext(
            message_bus=self.message_bus,
            shared_state=self.state_manager.state,  # 传递底层字典
            logger=logger,
            db_writer=DBWriterHelper(self.message_bus.get_client(ProcessName.SUPERVISOR))
        )
        self.message_router = MessageRouter(message_handler_ctx)
        
        # 创建数据库管理器
        self.db_write_queue = queue.Queue(maxsize=1000)
        self.db_manager = DBManager(self.db_write_queue)
        
        # 共享内存帧缓冲（Supervisor 作为唯一所有者）
        self.frame_buffer = None

        # 控制标志
        self.running = True
        self.shutdown_event = threading.Event()
        
        logger.info("=" * 60)
        logger.info("📡 VigiDoor Supervisor 初始化完成")
        logger.info(f"   设备 ID: {self.config_manager.device.id}")
        logger.info(f"   设备名称: {self.config_manager.device.name}")
        logger.info("=" * 60)
    
    def _ensure_db_initialized(self):
        """确保数据库已初始化"""
        from pathlib import Path
        from db.init_db import init_databases, ensure_migrations
        
        db_dir = Path("./data")
        config_db = db_dir / "config.db"
        
        if not config_db.exists():
            logger.info("📊 配置数据库不存在，开始初始化...")
            init_databases(db_dir)
            logger.info("✅ 数据库初始化完成")
        else:
            logger.info("📊 配置数据库已存在，跳过初始化")

        # 执行幂等迁移，确保新增表结构在已有数据库中存在
        ensure_migrations(db_dir)

    def _load_initial_arm_status(self) -> bool:
        """从数据库加载初始布撤防状态，无记录时默认撤防"""
        try:
            from db.reader import DBReader
            reader = DBReader()
            last_status = reader.get_last_arm_status()
            reader.close()
            if last_status is None:
                logger.info("📊 无布撤防记录，默认撤防状态")
                return False
            is_armed = last_status == 'arm'
            logger.info(f"📊 从数据库恢复布撤防状态: {'布防' if is_armed else '撤防'}")
            return is_armed
        except Exception as e:
            logger.warning(f"⚠️ 读取布撤防状态失败，默认撤防: {e}")
            return False
    
    def start(self):
        """启动所有服务"""
        logger.info("🚀 Supervisor 主服务启动中...")
        
        # 注册信号处理
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
        # 创建必要目录
        self._create_directories()

        # 创建共享内存帧缓冲（必须在子进程启动前创建）
        self._create_shared_memory()
        
        # 启动数据库管理器
        logger.info("📊 启动 DBManager...")
        self.db_manager.start()
        self.db_manager.schedule_cleanup()
        
        # 启动所有进程
        self.process_manager.start_all_processes()
        
        # 启动健康监控
        self.health_monitor.start_monitoring()
        
        # 启动消息处理线程
        self._start_message_consumer()

        # 延迟播放启动提示音（等待音频进程就绪）
        threading.Timer(5.0, self._play_startup_sound).start()
        
        # 进入主循环
        self._main_loop()
    
    def _play_startup_sound(self):
        """播放系统启动提示音"""
        try:
            self.message_bus.send(ProcessName.AUDIO_PROCESSOR, CommandMessage(
                cmd_type=MessageType.CMD_PLAY_AUDIO,
                target=ProcessName.AUDIO_PROCESSOR,
                cmd_data={'path': 'assets/audio/serverStar.mp3'}
            ))
            logger.info("🔊 系统启动提示音已发送")
        except Exception as e:
            logger.warning(f"播放启动提示音失败: {e}")

    def _create_directories(self):
        """创建必要的目录"""
        dirs = [
            './logs',
            './data/snapshots',
            './data/cache',
        ]
        for d in dirs:
            os.makedirs(d, exist_ok=True)

    def _create_shared_memory(self):
        """由 Supervisor 统一创建并持有共享内存帧缓冲（唯一所有者）"""
        cam = self.config_manager.camera
        try:
            self.frame_buffer = SharedFrameBuffer(
                width=cam.width,
                height=cam.height,
                name=cam.shared_memory_name,
                create=True
            )
            logger.info(f"✅ Supervisor 已创建共享内存帧缓冲: {cam.shared_memory_name}")
        except Exception as e:
            logger.error(f"❌ 创建共享内存帧缓冲失败: {e}")
            raise
    
    def _start_message_consumer(self):
        """启动消息处理线程"""
        thread = threading.Thread(
            target=self._message_consumer_thread,
            name="MessageConsumer",
            daemon=True
        )
        thread.start()
        logger.info("🧵 消息处理线程已启动")
    
    def _message_consumer_thread(self):
        """
        消息处理线程 - Supervisor作为普通消费者
        
        职责：
        1. 消费需要全局协调的消息
        2. 转发数据库写入请求
        3. 路由其他消息到对应处理器
        """
        logger.info("📬 Supervisor消息处理线程启动")
        
        supervisor_client = self.message_bus.get_client(ProcessName.SUPERVISOR)
        while self.running:
            try:
                msg = supervisor_client.receive(timeout=1)
                if msg:
                    self._handle_message(msg)
            except Exception as e:
                if self.running:
                    logger.debug(f"消息接收超时或错误: {e}")
                continue
    
    def _handle_message(self, msg: IPCMessage) -> None:
        """
        处理接收到的消息
        
        Args:
            msg: IPC 消息
        """        
        # 特殊处理：DB_WRITE 消息直接转发到 db_write_queue
        if msg.msg_type == MessageType.DB_WRITE:
            try:
                self.db_write_queue.put_nowait(msg.data)
                logger.debug(f"DB写入请求已转发: {msg.data.get('action')}")
            except Exception as e:
                logger.error(f"DB写入请求转发失败: {e}")
            return
        
        # 其他消息按原有逻辑处理
        # logger.info(f"📨 处理消息: {msg.msg_type}")
        self.message_router.dispatch(msg)
    
    def _main_loop(self):
        """主循环 - 只负责协调报警自动恢复"""
        logger.info("♻️  Supervisor 主循环启动")
        
        try:
            while self.running:
                # 检查报警/警戒自动恢复
                self.health_monitor.check_alarm_auto_reset()
                self.health_monitor.check_alert_auto_reset()
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("⚠️ 收到中断信号")
        finally:
            self._graceful_shutdown()
    
    def _signal_handler(self, signum, frame):
        """信号处理器"""
        logger.info(f"📨 收到信号 {signum}")
        self.running = False
        self.shutdown_event.set()
    
    def _graceful_shutdown(self):
        """优雅关闭所有服务"""
        logger.info("🛑 开始优雅关闭...")
        
        # 停止健康监控
        self.health_monitor.stop_monitoring()
        
        # 停止所有进程
        self.process_manager.stop_all_processes()
        
        # 关闭消息总线
        self.message_bus.close()
        logger.info("✅ 消息总线已关闭")
        
        # 停止数据库管理器
        logger.info("📊 停止 DBManager...")
        self.db_manager.stop()
        logger.info("✅ DBManager 已停止")

        # 清理共享内存（Supervisor 作为所有者负责 unlink）
        if self.frame_buffer:
            self.frame_buffer.cleanup()
            self.frame_buffer = None
        
        logger.info("✅ 所有服务已停止，Supervisor 退出")


if __name__ == '__main__':
    # 设置多进程启动方法
    mp.set_start_method('spawn', force=True)
    
    # 创建并启动 Supervisor
    supervisor = ProcessSupervisor()
    supervisor.start()
