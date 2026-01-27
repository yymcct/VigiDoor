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
from typing import Dict, List, Callable, Optional
from datetime import datetime

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.logger import setup_logger
from utils.ipc import IPCHelper

# 全局日志
logger = setup_logger('supervisor')


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
    进程监督者 - 系统的核心大脑
    
    职责：
    1. 管理所有子进程的生命周期
    2. 监控进程健康状态
    3. 自动重启崩溃进程
    4. 路由进程间消息
    5. 管理全局状态机
    """
    
    # 全局状态定义
    STATE_SAFE = "safe"      # 安全状态（绿灯）
    STATE_ALERT = "alert"    # 警戒状态（黄灯）
    STATE_ALARM = "alarm"    # 报警状态（红灯闪烁）
    
    def __init__(self, config_path: str = "./config.yaml"):
        # 加载配置
        self.config = self._load_config(config_path)
        
        # 进程管理
        self.processes: Dict[str, mp.Process] = {}
        self.process_configs: List[ProcessConfig] = []
        
        # 进程间通信
        self.ipc_queue = mp.Queue(maxsize=1000)
        self.shared_state = mp.Manager().dict({
            'global_state': self.STATE_SAFE,
            'device_id': self.config['device']['id'],
            'is_streaming': False,
            'last_heartbeat': {},
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
                name='device_controller',
                target=self._run_device_controller,
                critical=True,
                startup_delay=delays['device_controller']
            ),
            ProcessConfig(
                name='mqtt_client',
                target=self._run_mqtt_client,
                critical=True,
                startup_delay=delays['mqtt_client']
            ),
            ProcessConfig(
                name='audio_processor',
                target=self._run_audio_processor,
                critical=False,
                startup_delay=delays['audio_processor']
            ),
            ProcessConfig(
                name='ai_detector',
                target=self._run_ai_detector,
                critical=True,
                startup_delay=delays['ai_detector']
            ),
            ProcessConfig(
                name='stream_manager',
                target=self._run_stream_manager,
                critical=False,
                startup_delay=delays['stream_manager']
            ),
        ]
    
    def start(self):
        """启动 Supervisor 主服务"""
        logger.info("🚀 Supervisor 启动中...")
        
        # 注册信号处理
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
        # 创建必要的目录
        self._create_directories()
        
        # 启动所有子进程
        self._start_all_processes()
        
        # 启动监控线程
        self._start_monitor_threads()
        
        # 主循环（保持运行）
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
            # 创建进程
            process = mp.Process(
                target=self._process_wrapper,
                args=(config.target, config.name),
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
    
    def _process_wrapper(self, target_func: Callable, process_name: str):
        """
        进程包装器 - 捕获所有异常并记录
        这是每个子进程的入口点
        """
        try:
            # 重新配置日志（子进程需要独立配置）
            logger = setup_logger(process_name)
            logger.info(f"🔧 {process_name} 进程启动")
            
            # 执行实际业务逻辑
            target_func(self.ipc_queue, self.shared_state, self.config)
            
        except KeyboardInterrupt:
            logger.info(f"⚠️ {process_name} 收到中断信号")
        except Exception as e:
            logger.error(f"💥 {process_name} 进程崩溃: {e}", exc_info=True)
        finally:
            logger.info(f"🛑 {process_name} 进程退出")
    
    def _start_monitor_threads(self):
        """启动所有监控线程"""
        threads = [
            threading.Thread(target=self._heartbeat_monitor, name="HeartbeatMonitor", daemon=True),
            threading.Thread(target=self._message_router, name="MessageRouter", daemon=True),
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
    
    def _message_router(self):
        """消息路由线程 - 处理进程间通信"""
        logger.info("📬 消息路由线程启动")
        
        while self.running:
            try:
                # 从队列获取消息（阻塞等待）
                msg = self.ipc_queue.get(timeout=1)
                
                # 处理消息
                self._handle_message(msg)
                
            except:
                continue
    
    def _handle_message(self, msg: dict):
        """处理单条进程间消息"""
        msg_type = msg.get('type')
        
        if msg_type == 'anomaly_detected':
            # AI 检测到异常
            logger.warning(f"🚨 检测到异常: {msg.get('data')}")
            self._on_anomaly_detected(msg.get('data', {}))
            
        elif msg_type == 'audio_anomaly':
            # 检测到异常声音
            logger.warning(f"🔊 检测到异常声音")
            self._on_audio_anomaly(msg.get('data', {}))
            
        elif msg_type == 'mqtt_command':
            # 收到平台指令
            logger.info(f"📥 收到平台指令: {msg.get('action')}")
            self._on_platform_command(msg)
            
        elif msg_type == 'heartbeat':
            # 进程心跳
            process_name = msg.get('from')
            if process_name:
                self.shared_state['last_heartbeat'][process_name] = time.time()
        
        else:
            logger.debug(f"收到消息: {msg_type}")
    
    def _on_anomaly_detected(self, data: dict):
        """处理 AI 检测异常事件"""
        # 切换到报警状态
        self._set_global_state(self.STATE_ALARM)
        
        # 通知 MQTT 上报
        self.ipc_queue.put({
            'type': 'report_alarm',
            'to': 'mqtt_client',
            'data': data
        })
        
        # 通知硬件控制切换灯光
        self.ipc_queue.put({
            'type': 'set_light',
            'to': 'device_controller',
            'mode': 'alarm'
        })
    
    def _on_audio_anomaly(self, data: dict):
        """处理音频异常事件"""
        # 切换到警戒状态
        self._set_global_state(self.STATE_ALERT)
        
        # 通知硬件控制
        self.ipc_queue.put({
            'type': 'set_light',
            'to': 'device_controller',
            'mode': 'alert'
        })
    
    def _on_platform_command(self, msg: dict):
        """处理平台下发的指令"""
        action = msg.get('action')
        
        if action == 'start_stream':
            # 开始推流
            self.ipc_queue.put({
                'type': 'start_stream',
                'to': 'stream_manager',
                'data': msg.get('data')
            })
            
        elif action == 'stop_stream':
            # 停止推流
            self.ipc_queue.put({
                'type': 'stop_stream',
                'to': 'stream_manager'
            })
            
        elif action == 'remote_speak':
            # 远程喊话
            self.ipc_queue.put({
                'type': 'play_audio',
                'to': 'audio_processor',
                'data': msg.get('data')
            })
    
    def _set_global_state(self, new_state: str):
        """设置全局状态"""
        old_state = self.shared_state['global_state']
        if old_state != new_state:
            self.shared_state['global_state'] = new_state
            logger.info(f"🔄 全局状态切换: {old_state} → {new_state}")
    
    def _health_reporter(self):
        """健康状态上报线程"""
        logger.info("📊 健康上报线程启动")
        
        while self.running:
            try:
                # 采集系统指标
                metrics = self._collect_system_metrics()
                
                # 通过 MQTT 上报
                self.ipc_queue.put({
                    'type': 'report_health',
                    'to': 'mqtt_client',
                    'data': metrics
                })
                
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
        
        self.ipc_queue.put({
            'type': 'critical_alarm',
            'to': 'mqtt_client',
            'data': alarm_data
        })
    
    def _main_loop(self):
        """主循环 - 保持进程运行"""
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
            self.ipc_queue.put({
                'type': 'shutdown',
                'to': name
            })
        
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
        
        logger.info("✅ 所有进程已停止，Supervisor 退出")
    
    # ========== 子进程入口函数 ==========
    
    def _run_ai_detector(self, queue, shared_state, config):
        """AI 检测进程入口"""
        from modules.detector_process import AIDetectorProcess
        detector = AIDetectorProcess(queue, shared_state, config)
        detector.run()
    
    def _run_audio_processor(self, queue, shared_state, config):
        """音频处理进程入口"""
        from modules.audio_process import AudioProcessorProcess
        audio = AudioProcessorProcess(queue, shared_state, config)
        audio.run()
    
    def _run_mqtt_client(self, queue, shared_state, config):
        """MQTT 通信进程入口"""
        from modules.mqtt_process import MQTTClientProcess
        mqtt_client = MQTTClientProcess(queue, shared_state, config)
        mqtt_client.run()
    
    def _run_stream_manager(self, queue, shared_state, config):
        """流媒体进程入口"""
        from modules.stream_process import StreamManagerProcess
        stream = StreamManagerProcess(queue, shared_state, config)
        stream.run()
    
    def _run_device_controller(self, queue, shared_state, config):
        """硬件控制进程入口"""
        from modules.device_process import DeviceControllerProcess
        device = DeviceControllerProcess(queue, shared_state, config)
        device.run()


# ========== 程序入口 ==========

if __name__ == '__main__':
    # 设置多进程启动方法
    mp.set_start_method('spawn', force=True)
    
    # 创建并启动 Supervisor
    supervisor = ProcessSupervisor()
    supervisor.start()
