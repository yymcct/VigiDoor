#!/usr/bin/env python3
"""
VigiDoor Supervisor - 智慧安防门主进程管理器
负责启动、监控和管理所有子进程
"""

import multiprocessing as mp
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
        
        target_func(ipc_queue_or_client, shared_state, config)
        
    except KeyboardInterrupt:
        logger.info(f"⚠️ {process_name} 收到中断信号")
    except Exception as e:
        logger.error(f"💥 {process_name} 进程崩溃: {e}", exc_info=True)
    finally:
        logger.info(f"🛑 {process_name} 进程退出")


def run_ai_detector(queue, shared_state, config):
    """AI 检测进程入口"""
    from modules.detector_process import AIDetectorProcess
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
    from modules.stream_process import StreamManagerProcess
    stream = StreamManagerProcess(queue, shared_state, config)
    stream.run()


def run_device_controller(queue, shared_state, config):
    """硬件控制进程入口"""
    from modules.device_process import DeviceControllerProcess
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
        self.config = self._load_config(config_path)
        
        # 进程管理
        self.processes: Dict[str, mp.Process] = {}
        self.process_configs: List[ProcessConfig] = []
        
        self.message_bus = MessageBus(max_queue_size=1000)
        
        # 共享状态
        self.shared_state = mp.Manager().dict({
            'global_state': self.STATE_SAFE,
            'device_id': self.config['device']['id'],
            'is_streaming': False,
            'last_heartbeat': {},
            'start_time': time.time(),  # 添加启动时间，用于计算 uptime
        })
        
        # 控制标志
        self.running = True
        self.shutdown_event = threading.Event()
        
        # 初始化进程配置
        self._init_process_configs()
        
        logger.info("=" * 60)
        logger.info("📡 VigiDoor Supervisor 初始化完成")
        logger.info(f"   设备 ID: {self.config['device']['id']}")
        logger.info(f"   设备名称: {self.config['device']['name']}")
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
            # ProcessConfig(
            #     name='ai_detector',
            #     target=run_ai_detector,
            #     critical=True,
            #     startup_delay=delays['ai_detector']
            # ),
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
        msg_type = msg.msg_type
        if msg_type in (MessageType.HEARTBEAT, 'heartbeat'):
            self._handle_heartbeat(msg)
        elif msg_type in (MessageType.ANOMALY_DETECTED, 'anomaly_detected'):
            self._handle_anomaly_detected(msg)
        elif msg_type in (MessageType.AUDIO_ANOMALY, 'audio_anomaly'):
            self._handle_audio_anomaly(msg)
        elif msg_type in (MessageType.MQTT_COMMAND, 'mqtt_command'):
            self._handle_mqtt_command(msg)
        else:
            logger.debug(f"未处理的消息类型: {msg_type}")
    
    def _handle_heartbeat(self, msg: IPCMessage) -> None:
        """处理心跳消息"""
        process_name = msg.sender
        if process_name:
            self.shared_state['last_heartbeat'][process_name] = time.time()
            logger.debug(f"收到 {process_name} 心跳")
    
    def _handle_anomaly_detected(self, msg: IPCMessage) -> None:
        """处理 AI 检测到的异常"""
        data = msg.data or {}
        logger.warning(f"🚨 检测到异常: {data}")
        
        self._set_global_state('alarm')
        
        alarm_msg = CommandMessage(
            cmd_type=MessageType.REPORT_ALARM,
            target=ProcessName.MQTT_CLIENT,
            cmd_data=data
        )
        self.message_bus.send(ProcessName.MQTT_CLIENT, alarm_msg)
        
        light_msg = CommandMessage(
            cmd_type=MessageType.CMD_SET_LIGHT,
            target=ProcessName.DEVICE_CONTROLLER,
            cmd_data={'mode': 'alarm'}
        )
        self.message_bus.send(ProcessName.DEVICE_CONTROLLER, light_msg)
    
    def _handle_audio_anomaly(self, msg: IPCMessage) -> None:
        """处理音频异常"""
        data = msg.data or {}
        logger.warning("🔊 检测到异常声音")
        
        self._set_global_state('alert')
        
        light_msg = CommandMessage(
            cmd_type=MessageType.CMD_SET_LIGHT,
            target=ProcessName.DEVICE_CONTROLLER,
            cmd_data={'mode': 'alert'}
        )
        self.message_bus.send(ProcessName.DEVICE_CONTROLLER, light_msg)
    
    def _handle_mqtt_command(self, msg: IPCMessage) -> None:
        """处理平台下发的指令"""
        data = msg.data or {}
        action = data.get('action')
        logger.info(f"📥 收到平台指令: {action}")
        
        handler_map = {
            'remote_speak': self._handle_remote_speak,
        }
        
        handler = handler_map.get(action)
        if handler:
            handler(msg)
        else:
            logger.warning(f"未知的平台指令: {action}")
    
    def _handle_remote_speak(self, msg: IPCMessage) -> None:
        """处理远程喊话指令"""
        data = msg.data or {}
        audio_msg = CommandMessage(
            cmd_type=MessageType.CMD_PLAY_AUDIO,
            target=ProcessName.AUDIO_PROCESSOR,
            cmd_data=data
        )
        self.message_bus.send(ProcessName.AUDIO_PROCESSOR, audio_msg)
    
    def _set_global_state(self, state: str) -> None:
        """设置全局状态"""
        old_state = self.shared_state['global_state']
        if old_state != state:
            self.shared_state['global_state'] = state
            logger.info(f"🔄 全局状态切换: {old_state} → {state}")
    
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
        """优雅关闭所有进程"""
        logger.info("🛑 开始优雅关闭...")
        
        # 通知所有子进程准备关闭
        for name in self.processes.keys():
            shutdown_msg = ShutdownMessage(target=name, reason='supervisor_shutdown')
            self.message_bus.send(name, shutdown_msg)
        
        # 等待子进程优雅退出
        time.sleep(2)
        
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
        
        logger.info("✅ 所有进程已停止，Supervisor 退出")
    

if __name__ == '__main__':
    # 设置多进程启动方法
    mp.set_start_method('spawn', force=True)
    
    # 创建并启动 Supervisor
    supervisor = ProcessSupervisor()
    supervisor.start()
