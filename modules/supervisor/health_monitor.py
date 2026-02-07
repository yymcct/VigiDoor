"""
健康监控器 - 监控进程和系统健康状态

职责：
1. 进程心跳监控
2. 系统指标采集
3. 健康状态上报
4. 报警自动恢复检查
"""

import threading
import time
import logging
from typing import Optional, TYPE_CHECKING

from core.ipc.bus import IPCClient
from core.ipc.message import MessageType, StatusMessage, AlarmMessage, MessagePriority, CommandMessage
from core.ipc.registry import ProcessName
from .process_manager import ProcessManager
from .shared_state import SharedStateManager

if TYPE_CHECKING:
    from utils.config import ConfigManager
    
class HealthMonitor:
    """
    健康监控器
    
    在独立线程中监控系统和进程健康状态
    """
    
    def __init__(
        self,
        process_manager: ProcessManager,
        ipc_client: IPCClient,
        state_manager: SharedStateManager,
        config_manager: 'ConfigManager',
        logger: logging.Logger
    ):
        """
        初始化健康监控器
        
        Args:
            process_manager: 进程管理器
            ipc_client: IPC 客户端
            state_manager: 共享状态管理器
            config_manager: ConfigManager 实例
            logger: 日志记录器
        """
        self.process_manager = process_manager
        self.ipc_client = ipc_client
        self.state_manager = state_manager
        self.config_manager = config_manager
        self.logger = logger
        
        self.running = False
        self._threads = []
    
    # ==================== 监控启动/停止 ====================
    
    def start_monitoring(self) -> None:
        """启动所有监控线程"""
        self.running = True
        
        threads = [
            threading.Thread(
                target=self._heartbeat_monitor_thread,
                name="HeartbeatMonitor",
                daemon=True
            ),
            threading.Thread(
                target=self._health_reporter_thread,
                name="HealthReporter",
                daemon=True
            ),
        ]
        
        for thread in threads:
            thread.start()
            self._threads.append(thread)
            self.logger.info(f"🧵 监控线程 {thread.name} 已启动")
    
    def stop_monitoring(self) -> None:
        """停止所有监控线程"""
        self.logger.info("停止监控线程...")
        self.running = False
        
        # 等待线程退出
        for thread in self._threads:
            thread.join(timeout=2)
        
        self.logger.info("✅ 监控线程已停止")
    
    # ==================== 心跳监控 ====================
    
    def _heartbeat_monitor_thread(self) -> None:
        """心跳监控线程 - 检查所有子进程健康状态"""
        self.logger.info("💓 心跳监控线程启动")
        
        while self.running:
            try:
                for config in self.process_manager.get_all_configs():
                    process_alive = self.process_manager.is_process_alive(config.name)
                    
                    # 检查进程是否存活
                    if not process_alive:
                        process = self.process_manager.processes.get(config.name)
                        exit_code = process.exitcode if process else "N/A"
                        self.logger.warning(
                            f"⚠️ 检测到进程 {config.name} 已停止 (退出码: {exit_code})"
                        )
                        
                        # 尝试重启
                        if self.process_manager.can_restart(config):
                            self.logger.info(f"🔄 正在重启进程 {config.name}...")
                            self.process_manager.start_single_process(config)
                        else:
                            self.logger.error(
                                f"🚫 进程 {config.name} 重启次数超限，已放弃重启"
                            )
                            
                            # 如果是关键进程，发送严重告警
                            if config.critical:
                                self._send_critical_alarm(config.name)
                
                # 检查间隔
                heartbeat_interval = self.config_manager.supervisor.heartbeat_interval
                time.sleep(heartbeat_interval)
                
            except Exception as e:
                self.logger.error(f"心跳监控异常: {e}")
                time.sleep(5)
    
    def _send_critical_alarm(self, process_name: str) -> None:
        """
        发送严重告警
        
        Args:
            process_name: 崩溃的进程名称
        """
        alarm_data = {
            'level': 'CRITICAL',
            'message': f'关键进程 {process_name} 崩溃且无法重启',
            'timestamp': time.time(),
            'device_id': self.state_manager.get_device_id()
        }
        
        # TODO 服务器端适配
        msg = AlarmMessage(
            alarm_type=MessageType.CRITICAL_ALARM,
            alarm_data=alarm_data
        )
        msg.target = ProcessName.MQTT_CLIENT
        msg.priority = MessagePriority.CRITICAL
        self.ipc_client.send_message(msg)
    
    # ==================== 健康上报 ====================
    
    def _health_reporter_thread(self) -> None:
        """健康状态上报线程"""
        self.logger.info("📊 健康上报线程启动")
        
        while self.running:
            try:
                # 采集系统指标
                metrics = self.collect_system_metrics()
                
                # 通过 MQTT 上报
                msg = StatusMessage(
                    status_type=MessageType.REPORT_HEALTH,
                    status_data=metrics
                )
                msg.target = ProcessName.MQTT_CLIENT
                self.ipc_client.send_message(msg)
                self.logger.info(f"健康上报已发送: CPU={metrics.get('cpu_usage', 0):.1f}% MEM={metrics.get('memory_usage', 0):.1f}%")
                # 上报间隔
                report_interval = self.config_manager.monitoring.health_report_interval
                time.sleep(report_interval)
                
            except Exception as e:
                self.logger.error(f"健康上报异常: {e}")
                time.sleep(60)
     # TODO 服务器端适配
    def collect_system_metrics(self) -> dict:
        """
        采集系统健康指标
        
        Returns:
            系统指标字典
        """
        try:
            import psutil
            return {
                # 'timestamp': time.time(),
                'cpu_usage': psutil.cpu_percent(interval=1),
                # 'memory_usage': psutil.virtual_memory().percent,
               # 'disk_usage': psutil.disk_usage('/').percent,
                 'temperature': self._get_cpu_temperature(),
                # 'uptime': time.time() - psutil.boot_time(),
                # 'process_status': self.process_manager.get_process_status()
            }
        except Exception as e:
            self.logger.error(f"采集指标失败: {e}")
            return {'timestamp': time.time(), 'error': str(e)}
    
    def _get_cpu_temperature(self) -> float:
        """
        获取 CPU 温度（树莓派）
        
        Returns:
            CPU 温度（摄氏度）
        """
        try:
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                return float(f.read().strip()) / 1000.0
        except:
            return 0.0
    
    # ==================== 报警自动恢复 ====================
    
    def check_alarm_auto_reset(self) -> None:
        """检查并执行报警状态自动恢复"""
        try:
            # 只在报警状态下检查
            if not self.state_manager.is_alarm():
                return

            alarm_until = self.state_manager.get_alarm_until()
            if alarm_until <= 0:
                return

            # 检查是否到达恢复时间
            if time.time() >= alarm_until:
                self.state_manager.set_global_state(SharedStateManager.STATE_SAFE)
                self.state_manager.clear_alarm()
                self.logger.info("✅ 报警自动恢复：状态切换为 safe")

                # 发送灯光控制命令
                light_msg = CommandMessage(
                    cmd_type=MessageType.CMD_SET_LIGHT,
                    target=ProcessName.DEVICE_CONTROLLER,
                    cmd_data={'mode': 'safe'}
                )
                self.ipc_client.send_message(light_msg)
                
        except Exception as e:
            self.logger.error(f"报警自动恢复异常: {e}")
