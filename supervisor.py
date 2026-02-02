#!/usr/bin/env python3
"""
VigiDoor Supervisor - 智慧安防门主进程管理器
负责启动、监控和管理所有子进程
"""

import multiprocessing as mp
from multiprocessing import shared_memory
import signal
import time
import threading
import os
import sys
import yaml
from dataclasses import dataclass, field
from typing import Dict, List, Callable

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.logger import setup_logger

from core.ipc import MessageBus
from core.ipc.message import MessageType, IPCMessage, ShutdownMessage, CommandMessage
from core.ipc.registry import ProcessName
from modules.supervisor.handlers import SupervisorHandlerContext
from modules.supervisor.message_router import MessageRouter

logger = setup_logger('supervisor')


def process_wrapper(target_func: Callable, process_name: str, ipc_queue_or_client, shared_state, config: dict):
    """
    进程包装器 - 捕获所有异常并记录
    这是每个子进程的入口点（模块级别函数，避免 pickle 错误）
    
    Args:
        ipc_queue_or_client: IPCClient 实例
    """
    try:
        # 重新配置日志（子进程需要独立配置）
        logger = setup_logger(process_name)
        logger.info(f"🔧 {process_name} 进程启动")
        
        # 初始化 ALSA 配置（减少默认设备探测噪声）
        try:
            from utils.alsa import setup_alsa_defaults
            setup_alsa_defaults(logger=logger)
        except Exception as e:
            logger.warning(f"ALSA 配置初始化失败: {e}")

        # 初始化 ConfigManager（子进程需要独立初始化）
        try:
            from utils.config import ConfigManager
            ConfigManager.reset()  # 重置单例状态
            config_path = config.get('_config_path', 'config.yaml')
            ConfigManager.initialize(config_path)
            logger.info("✓ ConfigManager 已初始化")
        except Exception as e:
            logger.warning(f"ConfigManager 初始化失败: {e}")
        
        target_func(ipc_queue_or_client, shared_state, config)
        
    except KeyboardInterrupt:
        logger.info(f"⚠️ {process_name} 收到中断信号")
    except Exception as e:
        logger.error(f"💥 {process_name} 进程崩溃: {e}", exc_info=True)
    finally:
        logger.info(f"🛑 {process_name} 进程退出")


def run_ai_detector(queue, shared_state, config):
    """AI 检测进程入口"""
    from modules.detector import AIDetectorProcess
    detector = AIDetectorProcess(queue, shared_state, config)
    detector.run()


def run_audio_processor(queue, shared_state, config):
    """音频处理进程入口"""
    from modules.audio_process import AudioProcessorProcess
    audio = AudioProcessorProcess(queue, shared_state, config)
    audio.run()


def run_mqtt_client(queue, shared_state, config):
    """MQTT 通信进程入口"""
    from modules.mqtt_process import MQTTClientProcess
    mqtt_client = MQTTClientProcess(queue, shared_state, config)
    mqtt_client.run()


def run_stream_manager(queue, shared_state, config):
    """流媒体进程入口"""
    from modules.stream import StreamManagerProcess
    stream = StreamManagerProcess(queue, shared_state, config)
    stream.run()


def run_device_controller(queue, shared_state, config):
    """硬件控制进程入口"""
    from modules.device import DeviceControllerProcess
    device = DeviceControllerProcess(queue, shared_state, config)
    device.run()


def run_camera(queue, shared_state, config):
    """视频采集进程入口"""
    from modules.camera import CameraProcess
    camera = CameraProcess(queue, shared_state, config)
    camera.run()


@dataclass
class ProcessConfig:
    """进程配置"""
    name: str
    target: Callable
    restart_limit: int = 5        # 时间窗口内最大重启次数
    restart_window: int = 300     # 时间窗口（秒）
    critical: bool = True         # 是否关键进程
    startup_delay: float = 0      # 启动延迟（秒）
    restart_history: List[float] = field(default_factory=list)


class ProcessSupervisor:
    """
    进程监督者 - 系统协调中心
    
    职责：
    1. 管理所有子进程的生命周期
    2. 监控进程健康状态
    3. 自动重启崩溃进程
    4. 消费全局协调消息（作为普通消费者）
    5. 管理全局状态机
    """
    
    # 全局状态定义
    STATE_SAFE = "safe"      # 安全状态（绿灯）
    STATE_ALERT = "alert"    # 警戒状态（黄灯）
    STATE_ALARM = "alarm"    # 报警状态（红灯闪烁）
    
    def __init__(self, config_path: str = "./config.yaml"):
        # 初始化 ConfigManager（新的配置管理系统）
        from utils.config import ConfigManager
        ConfigManager.initialize(config_path)
        config_manager = ConfigManager.get_instance()
        
        # 向后兼容：保留原始配置字典
        self.config = config_manager.get_raw_dict()
        
        # 保存配置文件路径，以便子进程使用
        self.config['_config_path'] = config_path
        
        # 进程管理
        self.processes: Dict[str, mp.Process] = {}
        self.process_configs: List[ProcessConfig] = []
        
        self.message_bus = MessageBus(max_queue_size=1000)
        
        # 共享状态
        alarm_auto_reset_seconds = float(
            self.config.get('supervisor', {}).get('alarm_auto_reset_seconds', 0) or 0
        )
        self.shared_state = mp.Manager().dict({
            'global_state': self.STATE_SAFE,
            'device_id': self.config['device']['id'],
            'is_streaming': False,
            'last_heartbeat': {},
            'start_time': time.time(),  # 添加启动时间，用于计算 uptime
            'alarm_until': 0.0,
            'alarm_auto_reset_seconds': alarm_auto_reset_seconds,
        })

        self.message_handler_ctx = SupervisorHandlerContext(
            message_bus=self.message_bus,
            shared_state=self.shared_state,
            logger=logger
        )
        self.message_router = MessageRouter(self.message_handler_ctx)
        
        # 控制标志
        self.running = True
        self.shutdown_event = threading.Event()
        
        # 初始化进程配置
        self._init_process_configs()
        
        logger.info("=" * 60)
        logger.info("📡 VigiDoor Supervisor 初始化完成")
        logger.info(f"   设备 ID: {self.config['device']['id']}")
        logger.info(f"   设备名称: {self.config['device']['name']}")
        logger.info(f"   配置管理: ConfigManager (类型安全)")
        logger.info("=" * 60)
    
    def _load_config(self, config_path: str) -> dict:
        """加载配置文件"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"配置文件加载失败: {e}")
            sys.exit(1)
    
    def _init_process_configs(self):
        """初始化所有子进程配置"""
        delays = self.config['supervisor']['startup_delays']
        
        self.process_configs = [
            ProcessConfig(
                name='camera',
                target=run_camera,
                critical=True,
                startup_delay=delays.get('camera', 0)
            ),
            ProcessConfig(
                name='device_controller',
                target=run_device_controller,
                critical=True,
                startup_delay=delays['device_controller']
            ),
            ProcessConfig(
                name='mqtt_client',
                target=run_mqtt_client,
                critical=True,
                startup_delay=delays['mqtt_client']
            ),
            ProcessConfig(
                name='audio_processor',
                target=run_audio_processor,
                critical=False,
                startup_delay=delays['audio_processor']
            ),
            ProcessConfig(
                name='ai_detector',
                target=run_ai_detector,
                critical=True,
                startup_delay=delays['ai_detector']
            ),
            ProcessConfig(
                name='stream_manager',
                target=run_stream_manager,
                critical=False,
                startup_delay=delays['stream_manager']
            ),
        ]
    
    def start(self):
        logger.info("🚀 Supervisor 主服务启动中...")
        
        # 注册信号处理
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
        self._create_directories()
        
        self._start_all_processes()
        
        self._start_monitor_threads()
        
        self._main_loop()
    
    def _create_directories(self):
        """创建必要的目录"""
        dirs = [
            './logs',
            './data/snapshots',
            './data/cache',
        ]
        for d in dirs:
            os.makedirs(d, exist_ok=True)
    
    def _start_all_processes(self):
        """按顺序启动所有子进程"""
        logger.info("📦 开始启动子进程...")
        
        for config in self.process_configs:
            if config.startup_delay > 0:
                logger.info(f"⏳ 等待 {config.startup_delay}s 后启动 {config.name}")
                time.sleep(config.startup_delay)
            
            self._start_single_process(config)
    
    def _start_single_process(self, config: ProcessConfig) -> bool:
        """启动单个子进程"""
        try:
            ipc_obj = self.message_bus.get_client(config.name)
            
            process = mp.Process(
                target=process_wrapper,
                args=(config.target, config.name, ipc_obj, self.shared_state, self.config),
                name=config.name,
                daemon=False
            )
            
            process.start()
            self.processes[config.name] = process
            
            # 更新共享状态
            self.shared_state['last_heartbeat'][config.name] = time.time()
            
            logger.info(f"✅ 进程 {config.name} 启动成功 (PID: {process.pid})")
            return True
            
        except Exception as e:
            logger.error(f"❌ 进程 {config.name} 启动失败: {e}")
            return False
    
    def _start_monitor_threads(self):
        """启动所有监控线程"""
        threads = [
            threading.Thread(target=self._heartbeat_monitor, name="HeartbeatMonitor", daemon=True),
            threading.Thread(target=self._message_consumer, name="MessageConsumer", daemon=True),
            threading.Thread(target=self._health_reporter, name="HealthReporter", daemon=True),
        ]
        
        for thread in threads:
            thread.start()
            logger.info(f"🧵 监控线程 {thread.name} 已启动")
    
    def _heartbeat_monitor(self):
        """心跳监控线程 - 检查所有子进程健康状态"""
        logger.info("💓 心跳监控线程启动")
        
        while self.running:
            try:
                for config in self.process_configs:
                    process = self.processes.get(config.name)
                    
                    # 检查进程是否存活
                    if process is None or not process.is_alive():
                        exit_code = process.exitcode if process else "N/A"
                        logger.warning(
                            f"⚠️ 检测到进程 {config.name} 已停止 (退出码: {exit_code})"
                        )
                        
                        # 尝试重启
                        if self._can_restart(config):
                            logger.info(f"🔄 正在重启进程 {config.name}...")
                            self._start_single_process(config)
                        else:
                            logger.error(
                                f"🚫 进程 {config.name} 重启次数超限，已放弃重启"
                            )
                            
                            # 如果是关键进程，发送严重告警
                            if config.critical:
                                self._send_critical_alarm(config.name)
                
                # 检查间隔
                time.sleep(self.config['supervisor']['heartbeat_interval'])
                
            except Exception as e:
                logger.error(f"心跳监控异常: {e}")
                time.sleep(5)
    
    def _can_restart(self, config: ProcessConfig) -> bool:
        """判断是否允许重启（防止重启风暴）"""
        now = time.time()
        
        # 清理过期的重启记录
        config.restart_history = [
            t for t in config.restart_history
            if now - t < config.restart_window
        ]
        
        # 检查是否超限
        if len(config.restart_history) >= config.restart_limit:
            logger.error(
                f"进程 {config.name} 在 {config.restart_window}秒内"
                f"重启了 {len(config.restart_history)} 次，已达上限"
            )
            return False
        
        # 记录本次重启
        config.restart_history.append(now)
        return True
    
    def _message_consumer(self):
        """消息处理线程 - Supervisor作为普通消费者
        
        Supervisor只是一个特殊的消费者：
        1. 消费需要全局协调的消息（anomaly_detected, mqtt_command等）
        2. 改变全局状态（shared_state）
        3. 主动发送指令给其他进程
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
        """根据消息类型处理业务逻辑"""
        self.message_router.dispatch(msg)
    
    def _health_reporter(self):
        """健康状态上报线程"""
        logger.info("📊 健康上报线程启动")
        
        while self.running:
            try:
                # 采集系统指标
                metrics = self._collect_system_metrics()
                
                # 通过 MQTT 上报
                from core.ipc.message import StatusMessage
                msg = StatusMessage(
                    status_type=MessageType.REPORT_HEALTH,
                    status_data=metrics
                )
                msg.target = ProcessName.MQTT_CLIENT
                self.message_bus.send(ProcessName.MQTT_CLIENT, msg)
                
                # 每分钟上报一次
                time.sleep(self.config['monitoring']['health_report_interval'])
                
            except Exception as e:
                logger.error(f"健康上报异常: {e}")
                time.sleep(60)
    
    def _collect_system_metrics(self) -> dict:
        """采集系统健康指标"""
        try:
            import psutil
            return {
                'timestamp': time.time(),
                'cpu_usage': psutil.cpu_percent(interval=1),
                'memory_usage': psutil.virtual_memory().percent,
                'disk_usage': psutil.disk_usage('/').percent,
                'temperature': self._get_cpu_temperature(),
                'uptime': time.time() - psutil.boot_time(),
                'process_status': {
                    name: proc.is_alive() if proc else False
                    for name, proc in self.processes.items()
                }
            }
        except Exception as e:
            logger.error(f"采集指标失败: {e}")
            return {'timestamp': time.time(), 'error': str(e)}
    
    def _get_cpu_temperature(self) -> float:
        """获取 CPU 温度"""
        try:
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                return float(f.read().strip()) / 1000.0
        except:
            return 0.0
    
    def _send_critical_alarm(self, process_name: str):
        """发送严重告警"""
        alarm_data = {
            'level': 'CRITICAL',
            'message': f'关键进程 {process_name} 崩溃且无法重启',
            'timestamp': time.time(),
            'device_id': self.shared_state['device_id']
        }
        
        from core.ipc.message import AlarmMessage, MessagePriority
        msg = AlarmMessage(
            alarm_type=MessageType.CRITICAL_ALARM,
            alarm_data=alarm_data
        )
        msg.target = ProcessName.MQTT_CLIENT
        msg.priority = MessagePriority.CRITICAL
        self.message_bus.send(ProcessName.MQTT_CLIENT, msg)
    
    def _main_loop(self):
        logger.info("♻️  Supervisor 主循环启动")
        
        try:
            while self.running:
                self._check_alarm_auto_reset()
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("⚠️ 收到中断信号")
        finally:
            self._graceful_shutdown()

    def _check_alarm_auto_reset(self):
        """报警状态自动恢复"""
        try:
            if self.shared_state.get('global_state') != self.STATE_ALARM:
                return

            alarm_until = float(self.shared_state.get('alarm_until', 0) or 0)
            if alarm_until <= 0:
                return

            if time.time() >= alarm_until:
                self.shared_state['global_state'] = self.STATE_SAFE
                self.shared_state['alarm_until'] = 0
                logger.info("✅ 报警自动恢复：状态切换为 safe")

                light_msg = CommandMessage(
                    cmd_type=MessageType.CMD_SET_LIGHT,
                    target=ProcessName.DEVICE_CONTROLLER,
                    cmd_data={'mode': 'safe'}
                )
                self.message_bus.send(ProcessName.DEVICE_CONTROLLER, light_msg)
        except Exception as e:
            logger.error(f"报警自动恢复异常: {e}")
    
    def _signal_handler(self, signum, frame):
        """信号处理器"""
        logger.info(f"📨 收到信号 {signum}")
        self.running = False
        self.shutdown_event.set()
    
    def _graceful_shutdown(self):
        """优雅关闭所有进程"""
        logger.info("🛑 开始优雅关闭...")
        
        # 通知所有子进程准备关闭
        for name in self.processes.keys():
            shutdown_msg = ShutdownMessage(target=name, reason='supervisor_shutdown')
            self.message_bus.send(name, shutdown_msg)
        
        # 等待子进程优雅退出（最多 5 秒）
        graceful_deadline = time.time() + 5
        while time.time() < graceful_deadline:
            if not any(p.is_alive() for p in self.processes.values()):
                break
            for process in self.processes.values():
                process.join(timeout=0.2)
        
        # 强制终止所有子进程
        for name, process in self.processes.items():
            if process.is_alive():
                logger.info(f"  终止进程 {name}...")
                process.terminate()
                process.join(timeout=5)
                
                # 如果还不退出，强制杀死
                if process.is_alive():
                    logger.warning(f"  强制杀死进程 {name}")
                    process.kill()
        
        # 关闭消息总线
        self.message_bus.close()
        logger.info("✅ 消息总线已关闭")

        # 清理共享内存（防止资源泄漏警告）
        self._cleanup_shared_memory()
        
        logger.info("✅ 所有进程已停止，Supervisor 退出")

    def _cleanup_shared_memory(self):
        """清理共享内存残留（仅在退出时调用）"""
        shm_name = self.config.get('camera', {}).get('shared_memory_name')
        if not shm_name:
            return

        try:
            shm = shared_memory.SharedMemory(name=shm_name)
            shm.close()
            shm.unlink()
            logger.info(f"🧹 已清理共享内存: {shm_name}")
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.warning(f"清理共享内存失败: {e}")
    

if __name__ == '__main__':
    # 设置多进程启动方法
    mp.set_start_method('spawn', force=True)
    
    # 创建并启动 Supervisor
    supervisor = ProcessSupervisor()
    supervisor.start()
