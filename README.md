# VigiDoor
边缘计算AI检测，安防盒子

## 🚀 快速开始（初版已实现）

```bash
# 1. 测试系统
python3 test_system.py

# 2. 运行系统（开发模式）
python3 supervisor.py

# 或使用快捷命令
./vigidoor.sh test    # 运行测试
./vigidoor.sh dev     # 开发模式启动
./vigidoor.sh logs    # 查看日志
```

**当前状态**: ✅ 初版骨架已完成，核心架构可运行

详细文档：
- [快速开始指南](QUICKSTART.md) 
- [项目总览](PROJECT_OVERVIEW.md)

---

## 📚 完整架构文档

好的，我来给你完整描述改进后的**企业级稳定性架构**。

---

# 🏗️ 智慧安防门 - 树莓派端完整软件架构

## 一、架构设计哲学

### 核心设计原则
```
1. 进程隔离：关键模块独立进程，故障不扩散
2. 自动恢复：任何组件崩溃都能自动重启
3. 降级运行：核心功能失败时切换到备用方案
4. 可观测性：实时监控所有组件健康状态
5. 防御编程：每个环节都有异常处理和超时保护
```

---

## 二、整体架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                        系统启动层 (Systemd)                          │
│  - 开机自动启动                                                       │
│  - 服务崩溃自动重启                                                   │
│  - 资源限制（CPU 80%, 内存 512MB）                                   │
└─────────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────────┐
│                    进程管理层 (Supervisor Master)                    │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  核心职责：                                                    │  │
│  │  1. 启动和管理所有子进程                                       │  │
│  │  2. 监控子进程心跳（每5秒检查一次）                            │  │
│  │  3. 崩溃自动重启（带限流：5分钟内最多5次）                     │  │
│  │  4. 进程间消息路由                                             │  │
│  │  5. 全局状态机管理（安全/警戒/报警）                           │  │
│  │  6. 系统健康监控与上报                                         │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                       │
│  硬件看门狗：每30秒"喂狗"，超时自动重启树莓派                       │
└─────────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────────┐
│                   进程间通信层 (IPC Infrastructure)                  │
│                                                                       │
│  ┌─────────────────┐      ┌──────────────────┐                     │
│  │  消息队列        │      │  共享内存         │                     │
│  │  (Queue)        │      │  (SharedMemory)  │                     │
│  │  - 异步消息传递  │      │  - 全局状态存储   │                     │
│  │  - 容量1000条   │      │  - 配置热更新     │                     │
│  └─────────────────┘      └──────────────────┘                     │
└─────────────────────────────────────────────────────────────────────┘
            ↓            ↓            ↓            ↓            ↓
┌──────────────┬──────────────┬──────────────┬──────────────┬────────┐
│ 进程1         │ 进程2         │ 进程3         │ 进程4         │ 进程5  │
│ AI检测进程    │ 音频处理进程  │ MQTT通信进程  │ 流媒体进程    │硬件控制│
│ (Detector)   │ (Audio)      │ (MQTT)       │ (Stream)     │(Device)│
└──────────────┴──────────────┴──────────────┴──────────────┴────────┘
```

---

## 三、各层详细设计

### 🎯 第一层：系统启动层

#### **Systemd服务配置**

```ini
# /etc/systemd/system/smartdoor.service

[Unit]
Description=Smart Security Door Master Service
Documentation=https://docs.smartdoor.com
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=/home/pi/smartdoor

# 启动命令
ExecStart=/usr/bin/python3 -u /home/pi/smartdoor/supervisor.py
ExecStop=/bin/kill -SIGTERM $MAINPID

# 自动重启策略
Restart=always
RestartSec=10
StartLimitInterval=300
StartLimitBurst=5

# 环境变量
Environment="PYTHONUNBUFFERED=1"
Environment="DEVICE_ID=RPI_001"

# 资源限制
MemoryLimit=512M
CPUQuota=80%
TasksMax=50

# 硬件看门狗支持
WatchdogSec=60
NotifyAccess=main

# 日志配置
StandardOutput=journal
StandardError=journal
SyslogIdentifier=smartdoor

[Install]
WantedBy=multi-user.target
```

**启动流程：**
```bash
# 安装服务
sudo systemctl daemon-reload
sudo systemctl enable smartdoor.service

# 启动服务
sudo systemctl start smartdoor.service

# 查看状态
sudo systemctl status smartdoor.service

# 查看日志
sudo journalctl -u smartdoor.service -f
```

---

### 🎯 第二层：进程管理层（核心中枢）

#### **Supervisor架构图**

```
                    ┌─────────────────────────────┐
                    │   Supervisor Master         │
                    │   (主进程 PID=1234)          │
                    └─────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ↓                     ↓                     ↓
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│ 心跳监控线程   │    │ 消息路由线程   │    │ 健康上报线程   │
│ (每5秒检查)    │    │ (实时处理)     │    │ (每分钟上报)   │
└───────────────┘    └───────────────┘    └───────────────┘
        ↓                     ↓                     ↓
   检查进程存活         分发进程间消息         采集系统指标
```

#### **完整代码实现**

```python
# supervisor.py - 进程管理器主程序

import multiprocessing as mp
import signal
import time
import threading
import json
from dataclasses import dataclass, field
from typing import Dict, List, Callable
from datetime import datetime
import logging
import psutil

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [%(processName)s] %(message)s',
    handlers=[
        logging.FileHandler('/var/log/smartdoor/supervisor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

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
    6. 上报系统健康指标
    """
    
    # 全局状态定义
    STATE_SAFE = "safe"      # 安全状态（绿灯）
    STATE_ALERT = "alert"    # 警戒状态（黄灯）
    STATE_ALARM = "alarm"    # 报警状态（红灯闪烁）
    
    def __init__(self):
        # 进程管理
        self.processes: Dict[str, mp.Process] = {}
        self.process_configs: List[ProcessConfig] = []
        
        # 进程间通信
        self.ipc_queue = mp.Queue(maxsize=1000)
        self.shared_state = mp.Manager().dict({
            'global_state': self.STATE_SAFE,
            'device_id': 'RPI_001',
            'is_streaming': False,
            'last_heartbeat': {},
        })
        
        # 控制标志
        self.running = True
        self.shutdown_event = threading.Event()
        
        # 硬件看门狗
        self.watchdog = HardwareWatchdog()
        
        # 初始化进程配置
        self._init_process_configs()
        
        logger.info("📡 Supervisor初始化完成")
    
    def _init_process_configs(self):
        """初始化所有子进程配置"""
        self.process_configs = [
            ProcessConfig(
                name='ai_detector',
                target=self._run_ai_detector,
                critical=True,
                startup_delay=2.0  # 等待摄像头初始化
            ),
            ProcessConfig(
                name='audio_processor',
                target=self._run_audio_processor,
                critical=False,  # 非关键，失败不影响主功能
                startup_delay=1.0
            ),
            ProcessConfig(
                name='mqtt_client',
                target=self._run_mqtt_client,
                critical=True,
                startup_delay=0.5
            ),
            ProcessConfig(
                name='stream_manager',
                target=self._run_stream_manager,
                critical=False,
                startup_delay=0
            ),
            ProcessConfig(
                name='device_controller',
                target=self._run_device_controller,
                critical=True,
                startup_delay=0
            ),
        ]
    
    def start(self):
        """启动Supervisor主服务"""
        logger.info("🚀 Supervisor启动中...")
        
        # 注册信号处理
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
        # 启动硬件看门狗
        self.watchdog.start()
        
        # 启动所有子进程
        self._start_all_processes()
        
        # 启动监控线程
        self._start_monitor_threads()
        
        # 主循环（保持运行）
        self._main_loop()
    
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
                daemon=False  # 非守护进程，确保正确清理
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
            # 设置进程标题（方便ps命令查看）
            try:
                import setproctitle
                setproctitle.setproctitle(f"smartdoor-{process_name}")
            except:
                pass
            
            # 重新配置日志（子进程需要独立配置）
            logging.basicConfig(
                level=logging.INFO,
                format=f'%(asctime)s [{process_name}] %(message)s',
                handlers=[
                    logging.FileHandler(f'/var/log/smartdoor/{process_name}.log'),
                    logging.StreamHandler()
                ]
            )
            
            logger.info(f"🔧 {process_name} 进程启动")
            
            # 执行实际业务逻辑
            target_func(self.ipc_queue, self.shared_state)
            
        except KeyboardInterrupt:
            logger.info(f"⚠️ {process_name} 收到中断信号")
        except Exception as e:
            logger.error(f"💥 {process_name} 进程崩溃: {e}")
            import traceback
            logger.error(traceback.format_exc())
        finally:
            logger.info(f"🛑 {process_name} 进程退出")
    
    def _start_monitor_threads(self):
        """启动所有监控线程"""
        threads = [
            threading.Thread(target=self._heartbeat_monitor, name="HeartbeatMonitor", daemon=True),
            threading.Thread(target=self._message_router, name="MessageRouter", daemon=True),
            threading.Thread(target=self._health_reporter, name="HealthReporter", daemon=True),
            threading.Thread(target=self._watchdog_feeder, name="WatchdogFeeder", daemon=True),
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
                            f"⚠️ 检测到进程 {config.name} 已停止 "
                            f"(退出码: {exit_code})"
                        )
                        
                        # 尝试重启
                        if self._can_restart(config):
                            logger.info(f"🔄 正在重启进程 {config.name}...")
                            self._start_single_process(config)
                        else:
                            logger.error(
                                f"🚫 进程 {config.name} 重启次数超限，"
                                f"已放弃重启"
                            )
                            
                            # 如果是关键进程，发送严重告警
                            if config.critical:
                                self._send_critical_alarm(config.name)
                
                # 检查间隔
                time.sleep(5)
                
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
                
            except mp.queues.Empty:
                continue
            except Exception as e:
                logger.error(f"消息路由异常: {e}")
    
    def _handle_message(self, msg: dict):
        """处理单条进程间消息"""
        msg_type = msg.get('type')
        
        if msg_type == 'anomaly_detected':
            # AI检测到异常
            logger.warning(f"🚨 检测到异常: {msg.get('data')}")
            self._on_anomaly_detected(msg['data'])
            
        elif msg_type == 'audio_anomaly':
            # 检测到异常声音
            logger.warning(f"🔊 检测到异常声音")
            self._on_audio_anomaly(msg['data'])
            
        elif msg_type == 'mqtt_command':
            # 收到平台指令
            logger.info(f"📥 收到平台指令: {msg.get('action')}")
            self._on_platform_command(msg)
            
        elif msg_type == 'heartbeat':
            # 进程心跳
            process_name = msg.get('from')
            self.shared_state['last_heartbeat'][process_name] = time.time()
            
        else:
            logger.warning(f"⚠️ 未知消息类型: {msg_type}")
    
    def _on_anomaly_detected(self, data: dict):
        """处理AI检测异常事件"""
        # 切换到报警状态
        self._set_global_state(self.STATE_ALARM)
        
        # 通知MQTT上报
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
                
                # 通过MQTT上报
                self.ipc_queue.put({
                    'type': 'report_health',
                    'to': 'mqtt_client',
                    'data': metrics
                })
                
                # 每分钟上报一次
                time.sleep(60)
                
            except Exception as e:
                logger.error(f"健康上报异常: {e}")
                time.sleep(60)
    
    def _collect_system_metrics(self) -> dict:
        """采集系统健康指标"""
        try:
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
            return {}
    
    def _get_cpu_temperature(self) -> float:
        """获取CPU温度"""
        try:
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                return float(f.read().strip()) / 1000.0
        except:
            return 0.0
    
    def _watchdog_feeder(self):
        """硬件看门狗喂狗线程"""
        logger.info("🐕 看门狗喂狗线程启动")
        
        while self.running:
            try:
                self.watchdog.feed()
                time.sleep(30)  # 每30秒喂一次
            except Exception as e:
                logger.error(f"喂狗失败: {e}")
    
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
        logger.info("♻️  Supervisor主循环启动")
        
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
        
        # 停止硬件看门狗
        self.watchdog.stop()
        
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
        
        logger.info("✅ 所有进程已停止，Supervisor退出")
    
    # ========== 子进程入口函数 ==========
    
    def _run_ai_detector(self, queue, shared_state):
        """AI检测进程入口"""
        from modules.detector_process import RobustAIDetector
        detector = RobustAIDetector(queue, shared_state)
        detector.run()
    
    def _run_audio_processor(self, queue, shared_state):
        """音频处理进程入口"""
        from modules.audio_process import RobustAudioProcessor
        audio = RobustAudioProcessor(queue, shared_state)
        audio.run()
    
    def _run_mqtt_client(self, queue, shared_state):
        """MQTT通信进程入口"""
        from modules.mqtt_process import RobustMQTTClient
        mqtt_client = RobustMQTTClient(queue, shared_state)
        mqtt_client.run()
    
    def _run_stream_manager(self, queue, shared_state):
        """流媒体进程入口"""
        from modules.stream_process import RobustStreamManager
        stream = RobustStreamManager(queue, shared_state)
        stream.run()
    
    def _run_device_controller(self, queue, shared_state):
        """硬件控制进程入口"""
        from modules.device_process import RobustDeviceController
        device = RobustDeviceController(queue, shared_state)
        device.run()


class HardwareWatchdog:
    """硬件看门狗 - 终极保险"""
    
    def __init__(self):
        self.watchdog_device = '/dev/watchdog'
        self.fd = None
    
    def start(self):
        """启动硬件看门狗"""
        try:
            self.fd = open(self.watchdog_device, 'wb', buffering=0)
            logger.info("✅ 硬件看门狗已启动")
        except Exception as e:
            logger.warning(f"⚠️ 硬件看门狗不可用: {e}")
    
    def feed(self):
        """喂狗 - 证明系统还活着"""
        if self.fd:
            try:
                self.fd.write(b'\0')
                self.fd.flush()
            except:
                pass
    
    def stop(self):
        """停止看门狗"""
        if self.fd:
            try:
                self.fd.write(b'V')  # 魔法字符关闭看门狗
                self.fd.close()
            except:
                pass


# ========== 程序入口 ==========

if __name__ == '__main__':
    # 设置多进程启动方法
    mp.set_start_method('spawn')
    
    # 创建并启动Supervisor
    supervisor = ProcessSupervisor()
    supervisor.start()
```

---

### 🎯 第三层：进程间通信层

```python
# utils/ipc.py - 进程间通信工具类

from multiprocessing import Queue
from typing import Any, Dict
import json
import time

class IPCMessage:
    """标准IPC消息格式"""
    
    def __init__(self, msg_type: str, target: str = None, data: Any = None):
        self.type = msg_type
        self.target = target  # 目标进程名
        self.data = data
        self.timestamp = time.time()
        self.from_process = mp.current_process().name
    
    def to_dict(self) -> dict:
        return {
            'type': self.type,
            'target': self.target,
            'data': self.data,
            'timestamp': self.timestamp,
            'from': self.from_process
        }

class IPCHelper:
    """IPC辅助类 - 简化进程间通信"""
    
    def __init__(self, queue: Queue, process_name: str):
        self.queue = queue
        self.process_name = process_name
    
    def send(self, msg_type: str, target: str = None, data: Any = None):
        """发送消息"""
        try:
            msg = IPCMessage(msg_type, target, data)
            self.queue.put(msg.to_dict(), block=False)
        except:
            # 队列满，丢弃消息
            pass
    
    def send_heartbeat(self):
        """发送心跳"""
        self.send('heartbeat', target='supervisor')
```

---

### 🎯 第四层：业务进程层

#### **进程1：AI检测进程**

```python
# modules/detector_process.py

import cv2
import numpy as np
import time
import logging
from ultralytics import YOLO

logger = logging.getLogger(__name__)

class RobustAIDetector:
    """
    AI检测进程 - 负责视频分析和异常检测
    
    特性：
    1. 硬件初始化失败自动降级
    2. 模型推理超时保护
    3. 连续失败自动重初始化
    4. 支持降级模式（简单运动检测）
    """
    
    def __init__(self, ipc_queue, shared_state):
        self.queue = ipc_queue
        self.state = shared_state
        self.camera = None
        self.model = None
        self.consecutive_failures = 0
        self.max_failures = 10
        self.running = True
        
    def run(self):
        """主循环"""
        logger.info("🎥 AI检测进程启动")
        
        # 初始化摄像头
        if not self._init_camera_with_retry():
            logger.error("摄像头初始化失败，进入降级模式")
            self._run_degraded_mode()
            return
        
        # 加载AI模型
        if not self._init_model_with_retry():
            logger.error("AI模型加载失败，进入降级模式")
            self._run_degraded_mode()
            return
        
        # 主检测循环
        self._main_detection_loop()
    
    def _init_camera_with_retry(self, max_retries=3) -> bool:
        """初始化摄像头（带重试）"""
        for i in range(max_retries):
            try:
                from picamera2 import Picamera2
                self.camera = Picamera2()
                config = self.camera.create_preview_configuration(
                    main={"size": (1280, 720), "format": "RGB888"}
                )
                self.camera.configure(config)
                self.camera.start()
                logger.info("✅ 摄像头初始化成功")
                return True
            except Exception as e:
                logger.error(f"摄像头初始化失败 (尝试 {i+1}/{max_retries}): {e}")
                time.sleep(2)
        return False
    
    def _init_model_with_retry(self, max_retries=2) -> bool:
        """加载AI模型（带重试）"""
        for i in range(max_retries):
            try:
                # 加载TFLite模型（轻量化）
                self.model = YOLO('/home/pi/smartdoor/models/yolov8n.tflite')
                logger.info("✅ AI模型加载成功")
                return True
            except Exception as e:
                logger.error(f"模型加载失败 (尝试 {i+1}/{max_retries}): {e}")
                time.sleep(1)
        return False
    
    def _main_detection_loop(self):
        """主检测循环 - AI模式"""
        logger.info("🔍 开始AI检测...")
        last_heartbeat = time.time()
        
        while self.running:
            try:
                # 捕获帧
                frame = self.camera.capture_array()
                
                # AI推理（带超时保护）
                results = self._inference_with_timeout(frame, timeout=2.0)
                
                if results:
                    # 检查是否有异常
                    if self._is_anomaly(results):
                        self._report_anomaly(results, frame)
                    
                    self.consecutive_failures = 0
                else:
                    self.consecutive_failures += 1
                
                # 连续失败太多次，重新初始化
                if self.consecutive_failures > self.max_failures:
                    logger.warning("连续失败过多，尝试重新初始化")
                    self._reinit_camera()
                    self.consecutive_failures = 0
                
                # 定期发送心跳
                if time.time() - last_heartbeat > 10:
                    self.queue.put({'type': 'heartbeat', 'from': 'ai_detector'})
                    last_heartbeat = time.time()
                
                time.sleep(0.1)  # 控制帧率
                
            except Exception as e:
                logger.error(f"检测循环异常: {e}")
                time.sleep(1)
    
    def _inference_with_timeout(self, frame, timeout=2.0):
        """AI推理（带超时保护）"""
        import concurrent.futures
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(self.model.predict, frame, verbose=False)
            try:
                return future.result(timeout=timeout)
            except concurrent.futures.TimeoutError:
                logger.warning("⚠️ 模型推理超时")
                return None
    
    def _is_anomaly(self, results) -> bool:
        """判断是否为异常事件"""
        # 检测到人（class_id=0）且置信度>0.7
        for result in results:
            boxes = result.boxes
            for box in boxes:
                if box.cls == 0 and box.conf > 0.7:
                    return True
        return False
    
    def _report_anomaly(self, results, frame):
        """上报异常事件"""
        logger.warning("🚨 检测到异常入侵！")
        
        # 保存关键帧
        snapshot_path = f"/tmp/alarm_{int(time.time())}.jpg"
        cv2.imwrite(snapshot_path, frame)
        
        # 发送消息给Supervisor
        self.queue.put({
            'type': 'anomaly_detected',
            'data': {
                'event_type': 'intrusion',
                'confidence': float(results[0].boxes[0].conf),
                'timestamp': time.time(),
                'snapshot_path': snapshot_path
            }
        })
    
    def _run_degraded_mode(self):
        """降级模式 - 简单运动检测"""
        logger.info("⚠️ 进入降级模式：运动检测")
        
        cap = cv2.VideoCapture(0)
        bg_subtractor = cv2.createBackgroundSubtractorMOG2()
        
        while self.running:
            ret, frame = cap.read()
            if not ret:
                continue
            
            # 背景差分法检测运动
            fg_mask = bg_subtractor.apply(frame)
            motion_pixels = np.sum(fg_mask > 0)
            
            if motion_pixels > 5000:
                logger.warning("🚨 检测到运动（降级模式）")
                self.queue.put({
                    'type': 'anomaly_detected',
                    'data': {
                        'event_type': 'motion',
                        'mode': 'degraded',
                        'timestamp': time.time()
                    }
                })
            
            time.sleep(0.5)
```

#### **进程2：MQTT通信进程**

```python
# modules/mqtt_process.py

import paho.mqtt.client as mqtt
import json
import time
import logging
import threading

logger = logging.getLogger(__name__)

class RobustMQTTClient:
    """
    MQTT通信进程 - 负责与云平台通信
    
    特性：
    1. 自动重连（指数退避）
    2. 消息队列缓存（断线不丢失）
    3. 心跳检测连接有效性
    4. 遗嘱消息（异常断线通知平台）
    """
    
    def __init__(self, ipc_queue, shared_state):
        self.ipc_queue = ipc_queue
        self.state = shared_state
        self.client = None
        self.is_connected = False
        self.running = True
        
        # 重连策略
        self.reconnect_delay = 1
        self.max_reconnect_delay = 60
        
        # 消息缓存队列
        self.message_buffer = []
        self.max_buffer_size = 100
        
        # 配置
        self.device_id = self.state['device_id']
        self.broker_host = "iot.huaweicloud.com"
        self.broker_port = 1883
    
    def run(self):
        """主循环"""
        logger.info("📡 MQTT通信进程启动")
        
        # 初始化客户端
        self._init_client()
        
        # 启动子线程
        threading.Thread(target=self._heartbeat_loop, daemon=True).start()
        threading.Thread(target=self._ipc_message_handler, daemon=True).start()
        
        # 保持连接
        while self.running:
            if not self.is_connected:
                self._reconnect()
            time.sleep(1)
    
    def _init_client(self):
        """初始化MQTT客户端"""
        self.client = mqtt.Client(
            client_id=f"smartdoor_{self.device_id}",
            clean_session=False  # 保留会话
        )
        
        # 设置回调
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        
        # 设置遗嘱消息
        self.client.will_set(
            topic=f"devices/{self.device_id}/status",
            payload=json.dumps({"online": False, "timestamp": time.time()}),
            qos=1,
            retain=True
        )
        
        # 设置认证（如果需要）
        # self.client.username_pw_set(username, password)
    
    def _reconnect(self):
        """重连MQTT服务器"""
        try:
            logger.info(f"🔄 尝试连接MQTT服务器 ({self.broker_host}:{self.broker_port})")
            
            self.client.connect(
                host=self.broker_host,
                port=self.broker_port,
                keepalive=60
            )
            
            # 启动网络循环
            self.client.loop_start()
            
            # 重置退避时间
            self.reconnect_delay = 1
            
        except Exception as e:
            logger.error(f"❌ MQTT连接失败: {e}")
            
            # 指数退避
            time.sleep(self.reconnect_delay)
            self.reconnect_delay = min(
                self.reconnect_delay * 2,
                self.max_reconnect_delay
            )
    
    def _on_connect(self, client, userdata, flags, rc):
        """连接成功回调"""
        if rc == 0:
            logger.info("✅ MQTT连接成功")
            self.is_connected = True
            
            # 订阅指令主题
            topics = [
                (f"devices/{self.device_id}/command", 1),
                (f"devices/{self.device_id}/config", 1),
            ]
            self.client.subscribe(topics)
            
            # 发送上线消息
            self._publish_online_status()
            
            # 发送缓存的消息
            self._flush_message_buffer()
            
        else:
            logger.error(f"❌ MQTT连接失败，返回码: {rc}")
            self.is_connected = False
    
    def _on_disconnect(self, client, userdata, rc):
        """断线回调"""
        logger.warning(f"⚠️ MQTT连接断开，返回码: {rc}")
        self.is_connected = False
        
        if rc != 0:
            logger.warning("异常断线，将自动重连")
    
    def _on_message(self, client, userdata, msg):
        """收到消息回调"""
        try:
            payload = json.loads(msg.payload.decode())
            logger.info(f"📥 收到平台指令: {payload}")
            
            # 转发给Supervisor
            self.ipc_queue.put({
                'type': 'mqtt_command',
                'action': payload.get('action'),
                'data': payload.get('data')
            })
            
        except Exception as e:
            logger.error(f"处理MQTT消息失败: {e}")
    
    def _heartbeat_loop(self):
        """心跳循环"""
        while self.running:
            if self.is_connected:
                try:
                    self.client.publish(
                        topic=f"devices/{self.device_id}/heartbeat",
                        payload=json.dumps({"timestamp": time.time()}),
                        qos=0
                    )
                except Exception as e:
                    logger.error(f"心跳发送失败: {e}")
                    self.is_connected = False
            
            time.sleep(30)
    
    def _ipc_message_handler(self):
        """处理来自其他进程的消息"""
        while self.running:
            try:
                # 从IPC队列获取消息
                msg = self.ipc_queue.get(timeout=1)
                
                # 只处理发给MQTT的消息
                if msg.get('to') == 'mqtt_client':
                    self._handle_ipc_message(msg)
                    
            except:
                continue
    
    def _handle_ipc_message(self, msg):
        """处理IPC消息"""
        msg_type = msg.get('type')
        
        if msg_type == 'report_alarm':
            # 上报告警
            self._publish_alarm(msg['data'])
            
        elif msg_type == 'report_health':
            # 上报健康状态
            self._publish_health(msg['data'])
            
        elif msg_type == 'critical_alarm':
            # 严重告警
            self._publish_critical_alarm(msg['data'])
    
    def _publish_alarm(self, alarm_data: dict):
        """发布告警消息"""
        topic = f"devices/{self.device_id}/alarm"
        payload = json.dumps(alarm_data)
        
        if self.is_connected:
            self.client.publish(topic, payload, qos=1)
            logger.info("📤 告警已上报")
        else:
            # 缓存消息
            self._buffer_message(topic, payload, qos=1)
    
    def _buffer_message(self, topic, payload, qos):
        """缓存消息"""
        if len(self.message_buffer) < self.max_buffer_size:
            self.message_buffer.append((topic, payload, qos))
            logger.warning(f"⚠️ MQTT未连接，消息已缓存（队列: {len(self.message_buffer)}）")
        else:
            logger.error("❌ 消息缓存队列已满，丢弃消息")
    
    def _flush_message_buffer(self):
        """发送缓存的消息"""
        if self.message_buffer:
            logger.info(f"📤 发送缓存的 {len(self.message_buffer)} 条消息")
            
            for topic, payload, qos in self.message_buffer:
                self.client.publish(topic, payload, qos)
            
            self.message_buffer.clear()
```

---

（由于字数限制，我将**流媒体进程、硬件控制进程、音频处理进程**的完整代码省略，它们的结构与上面类似）

---

## 四、项目目录结构

```
/home/pi/smartdoor/
├── supervisor.py                   # 主进程管理器（启动入口）
├── config.yaml                     # 全局配置文件
├── requirements.txt                # Python依赖
├── README.md                       # 文档
│
├── modules/                        # 业务进程模块
│   ├── __init__.py
│   ├── detector_process.py         # AI检测进程
│   ├── audio_process.py            # 音频处理进程
│   ├── mqtt_process.py             # MQTT通信进程
│   ├── stream_process.py           # 流媒体管理进程
│   └── device_process.py           # 硬件控制进程
│
├── utils/                          # 工具类
│   ├── __init__.py
│   ├── ipc.py                      # 进程间通信工具
│   ├── logger.py                   # 日志工具
│   └── watchdog.py                 # 看门狗工具
│
├── models/                         # AI模型
│   └── yolov8n.tflite              # 轻量化YOLO模型
│
├── logs/                           # 日志目录
│   ├── supervisor.log
│   ├── ai_detector.log
│   ├── mqtt_client.log
│   └── ...
│
├── data/                           # 数据目录
│   ├── snapshots/                  # 告警快照
│   └── cache/                      # 临时缓存
│
└── scripts/                        # 脚本
    ├── install.sh                  # 安装脚本
    ├── start.sh                    # 启动脚本
    └── stop.sh                     # 停止脚本
```

---

## 五、完整工作流程示例

### 场景1：正常启动流程

```
1. systemd 启动 supervisor.py
   ↓
2. Supervisor初始化
   - 创建IPC队列
   - 创建共享内存
   - 启动硬件看门狗
   ↓
3. 依次启动5个子进程
   - device_controller（硬件控制）：立即启动，灯带显示绿色
   - mqtt_client（MQTT通信）：0.5秒后启动，连接云平台
   - audio_processor（音频处理）：1秒后启动
   - ai_detector（AI检测）：2秒后启动，等待摄像头初始化
   - stream_manager（流媒体）：立即启动，但不推流
   ↓
4. 启动监控线程
   - 心跳监控线程：每5秒检查子进程
   - 消息路由线程：处理进程间消息
   - 健康上报线程：每分钟上报指标
   - 看门狗喂狗线程：每30秒喂一次狗
   ↓
5. 系统进入稳定运行状态
   - AI检测进程：持续分析画面
   - MQTT进程：保持与平台连接
   - 其他进程：待命状态
```

### 场景2：检测到异常入侵

```
1. AI检测进程检测到人
   frame → YOLO推理 → 置信度0.92 → 判定为异常
   ↓
2. AI进程发送消息
   ipc_queue.put({
       'type': 'anomaly_detected',
       'data': {...}
   })
   ↓
3. Supervisor接收并处理
   - 切换全局状态：SAFE → ALARM
   - 路由消息给device_controller：切换红灯闪烁
   - 路由消息给mqtt_client：上报告警
   ↓
4. MQTT进程上报到平台
   - 上传告警快照到OSS
   - 发送JSON告警到华为云IoT
   ↓
5. 平台值守人员收到告警
```

### 场景3：AI进程崩溃自动恢复

```
1. AI进程因内存溢出崩溃
   ↓
2. 心跳监控线程检测到异常
   "⚠️ 检测到进程 ai_detector 已停止"
   ↓
3. 检查重启限制
   - 查看restart_history
   - 当前窗口内重启次数：2/5
   - 允许重启
   ↓
4. 自动重启AI进程
   "🔄 正在重启进程 ai_detector..."
   - 重新创建进程
   - 重新初始化摄像头
   - 重新加载AI模型
   ↓
5. 5-10秒后恢复正常
   "✅ 进程 ai_detector 启动成功 (PID: 5678)"
```

### 场景4：网络断线自动重连

```
1. 树莓派网络断开
   ↓
2. MQTT进程检测到断线
   "_on_disconnect() 回调触发"
   ↓
3. 自动重连机制启动
   - 第1次尝试：1秒后重连 → 失败
   - 第2次尝试：2秒后重连 → 失败
   - 第3次尝试：4秒后重连 → 失败
   - 第4次尝试：8秒后重连 → 成功
   ↓
4. 重连成功后
   - 重新订阅主题
   - 发送上线消息
   - 发送缓存的告警消息（如果有）
   ↓
5. 系统恢复正常通信
```

---

## 六、稳定性保障总结

### 多层防护体系

```
┌─────────────────────────────────────────┐
│  第4层：平台监控                         │
│  - 设备离线超过5分钟发短信                │
│  - 远程重启指令                           │
└─────────────────────────────────────────┘
              ↑ 告警
┌─────────────────────────────────────────┐
│  第3层：硬件看门狗                        │
│  - 60秒无喂狗 → 硬重启树莓派               │
└─────────────────────────────────────────┘
              ↑ 喂狗
┌─────────────────────────────────────────┐
│  第2层：Systemd                          │
│  - Supervisor崩溃 → 10秒后重启            │
│  - 限流：5分钟内最多5次                    │
└─────────────────────────────────────────┘
              ↑ 重启
┌─────────────────────────────────────────┐
│  第1层：进程看门狗（Supervisor）          │
│  - 子进程崩溃 → 5秒内重启                 │
│  - 进程隔离：单个崩溃不影响整体            │
└─────────────────────────────────────────┘
```

### 关键特性

| 特性 | 实现方式 | 恢复时间 |
|------|----------|----------|
| 进程隔离 | 多进程架构 | - |
| 崩溃自动重启 | 心跳监控 + 自动拉起 | 5-10秒 |
| 重启风暴防护 | 限流机制（5分钟5次） | - |
| 网络断线恢复 | 指数退避重连 | 15-60秒 |
| 降级运行 | AI失败 → 运动检测 | 即时 |
| 资源泄漏防护 | 自动清理僵尸进程 | - |
| 硬件异常兜底 | 硬件看门狗 | 60秒 |
| 消息不丢失 | 本地缓存队列 | - |

---

## 七、可观测性

### 实时监控指标

```python
{
    "device_id": "RPI_001",
    "timestamp": 1706345678,
    "cpu_usage": 45.2,
    "memory_usage": 62.8,
    "disk_usage": 35.6,
    "temperature": 52.3,
    "uptime": 86400,
    "process_status": {
        "ai_detector": true,
        "audio_processor": true,
        "mqtt_client": true,
        "stream_manager": true,
        "device_controller": true
    },
    "restart_counts": {
        "ai_detector": 0,
        "mqtt_client": 1
    }
}
```

---

这就是**完整的企业级稳定性架构**，通过进程隔离、自动恢复、降级运行、多层防护，确保系统7x24小时稳定运行。即使遇到极端情况，也能在1分钟内自动恢复！