"""
进程管理器 - 负责进程的启动、停止、重启

职责：
1. 进程启动/停止/重启
2. 进程状态查询
3. 重启策略控制（防止重启风暴）
4. 进程优雅关闭
"""

import multiprocessing as mp
import time
from typing import Dict, List, Optional, TYPE_CHECKING
import logging

from core.ipc import MessageBus
from core.ipc.message import ShutdownMessage
from .process_registry import ProcessConfig, process_wrapper
from .shared_state import SharedStateManager

if TYPE_CHECKING:
    from utils.config import ConfigManager
    
    
class ProcessManager:
    """
    进程管理器
    
    管理所有子进程的生命周期，包括启动、监控、重启和停止
    """
    
    def __init__(
        self, 
        message_bus: MessageBus,    
        state_manager: SharedStateManager,
        process_configs: List[ProcessConfig],
        config_path: str,
        logger: logging.Logger
    ):
        """
        初始化进程管理器
        
        Args:
            message_bus: 消息总线
            state_manager: 共享状态管理器
            process_configs: 进程配置列表
            config_path: 配置文件路径
            logger: 日志记录器
        """
        self.message_bus = message_bus
        self.state_manager = state_manager
        self.process_configs = process_configs
        self.config_path = config_path
        self.logger = logger
        
        self.processes: Dict[str, mp.Process] = {}
    
    # ==================== 进程启动 ====================
    
    def start_all_processes(self) -> None:
        """按顺序启动所有子进程"""
        self.logger.info("📦 开始启动子进程...")
        
        for config in self.process_configs:
            if config.startup_delay > 0:
                self.logger.info(f"⏳ 等待 {config.startup_delay}s 后启动 {config.name}")
                time.sleep(config.startup_delay)
            
            self.start_single_process(config)
    
    def start_single_process(self, config: ProcessConfig) -> bool:
        """
        启动单个子进程
        
        Args:
            config: 进程配置
            
        Returns:
            是否启动成功
        """
        try:
            ipc_obj = self.message_bus.get_client(config.name)
            
            process = mp.Process(
                target=process_wrapper,
                args=(
                    config.target, 
                    config.name, 
                    ipc_obj, 
                    self.state_manager.state,  # 传递底层字典
                    self.config_path  # 传递配置文件路径
                ),
                name=config.name,
                daemon=False
            )
            
            process.start()
            self.processes[config.name] = process
            
            # 更新共享状态
            self.state_manager.update_heartbeat(config.name)
            
            self.logger.info(f"✅ 进程 {config.name} 启动成功 (PID: {process.pid})")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 进程 {config.name} 启动失败: {e}")
            return False
    
    def restart_process(self, process_name: str) -> bool:
        """
        重启指定进程
        
        Args:
            process_name: 进程名称
            
        Returns:
            是否重启成功
        """
        config = self._get_process_config(process_name)
        if not config:
            self.logger.error(f"未找到进程配置: {process_name}")
            return False
        
        # 停止旧进程
        old_process = self.processes.get(process_name)
        if old_process and old_process.is_alive():
            self.logger.info(f"正在停止进程 {process_name}...")
            old_process.terminate()
            old_process.join(timeout=3)
            
            if old_process.is_alive():
                self.logger.warning(f"强制杀死进程 {process_name}")
                old_process.kill()
        
        # 启动新进程
        return self.start_single_process(config)
    
    # ==================== 进程停止 ====================
    
    def stop_all_processes(self, graceful_timeout: float = 5.0) -> None:
        """
        停止所有进程
        
        Args:
            graceful_timeout: 优雅退出的等待时间（秒）
        """
        self.logger.info("🛑 开始停止所有进程...")
        
        # 通知所有子进程准备关闭
        for name in self.processes.keys():
            shutdown_msg = ShutdownMessage(target=name, reason='supervisor_shutdown')
            self.message_bus.send(name, shutdown_msg)
        
        # 等待子进程优雅退出
        graceful_deadline = time.time() + graceful_timeout
        while time.time() < graceful_deadline:
            if not any(p.is_alive() for p in self.processes.values()):
                self.logger.info("✅ 所有进程已优雅退出")
                return
            
            for process in self.processes.values():
                process.join(timeout=0.2)
        
        # 强制终止所有子进程
        for name, process in self.processes.items():
            if process.is_alive():
                self.logger.info(f"  终止进程 {name}...")
                process.terminate()
                process.join(timeout=5)
                
                # 如果还不退出，强制杀死
                if process.is_alive():
                    self.logger.warning(f"  强制杀死进程 {name}")
                    process.kill()
        
        self.logger.info("✅ 所有进程已停止")
    
    # ==================== 进程状态查询 ====================
    
    def is_process_alive(self, process_name: str) -> bool:
        """
        检查进程是否存活
        
        Args:
            process_name: 进程名称
            
        Returns:
            是否存活
        """
        process = self.processes.get(process_name)
        return process is not None and process.is_alive()
    
    def get_process_status(self) -> Dict[str, dict]:
        """
        获取所有进程状态
        
        Returns:
            进程状态字典 {进程名: {alive, pid, exitcode}}
        """
        status = {}
        for name, process in self.processes.items():
            status[name] = {
                'alive': process.is_alive() if process else False,
                'pid': process.pid if process else None,
                'exitcode': process.exitcode if process else None
            }
        return status
    
    def get_dead_processes(self) -> List[str]:
        """
        获取所有已停止的进程名称列表
        
        Returns:
            已停止的进程名称列表
        """
        dead = []
        for name, process in self.processes.items():
            if process is None or not process.is_alive():
                dead.append(name)
        return dead
    
    # ==================== 重启策略控制 ====================
    
    def can_restart(self, config: ProcessConfig) -> bool:
        """
        判断是否允许重启（防止重启风暴）
        
        Args:
            config: 进程配置
            
        Returns:
            是否允许重启
        """
        now = time.time()
        
        # 清理过期的重启记录
        config.restart_history = [
            t for t in config.restart_history
            if now - t < config.restart_window
        ]
        
        # 检查是否超限
        if len(config.restart_history) >= config.restart_limit:
            self.logger.error(
                f"进程 {config.name} 在 {config.restart_window}秒内"
                f"重启了 {len(config.restart_history)} 次，已达上限"
            )
            return False
        
        # 记录本次重启
        config.restart_history.append(now)
        return True
    
    # ==================== 辅助方法 ====================
    
    def _get_process_config(self, process_name: str) -> Optional[ProcessConfig]:
        """
        根据进程名称获取配置
        
        Args:
            process_name: 进程名称
            
        Returns:
            进程配置，如果不存在返回 None
        """
        for config in self.process_configs:
            if config.name == process_name:
                return config
        return None
    
    def get_all_configs(self) -> List[ProcessConfig]:
        """获取所有进程配置"""
        return self.process_configs
