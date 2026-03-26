"""
进程注册表 - 集中管理所有进程的入口函数和配置

这个模块包含：
1. 所有子进程的入口函数（run_xxx）
2. 进程包装器（process_wrapper）
3. 进程配置数据类（ProcessConfig）
4. 进程配置列表生成函数
"""

from dataclasses import dataclass, field
from typing import Callable, List, TYPE_CHECKING
import os
import sys

from core.process_context import ProcessContext

if TYPE_CHECKING:
    from utils.config import ConfigManager


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


def process_wrapper(target_func: Callable, process_name: str, ipc_queue_or_client, shared_state, config_path: str):
    """
    进程包装器 - 捕获所有异常并记录
    这是每个子进程的入口点（模块级别函数，避免 pickle 错误）

    构建 ProcessContext 后统一传入目标函数，消除各进程签名差异。

    Args:
        target_func: 目标进程函数
        process_name: 进程名称
        ipc_queue_or_client: IPCClient 实例
        shared_state: 共享状态字典
        config_path: 配置文件路径
    """
    # 添加项目根目录到 Python 路径（子进程需要）
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

    from utils.logger import setup_logger

    try:
        # 重新配置日志（子进程需要独立配置）
        logger = setup_logger(process_name)
        logger.info(f"🔧 {process_name} 进程启动")

        # 初始化 ConfigManager（子进程需要独立初始化）
        try:
            from utils.config import ConfigManager
            ConfigManager.reset()  # 重置单例状态
            ConfigManager.initialize(config_path)
            logger.info("✓ ConfigManager 已初始化")
        except Exception as e:
            logger.warning(f"ConfigManager 初始化失败: {e}")

        config_manager = ConfigManager.get_instance()

        ctx = ProcessContext(
            ipc=ipc_queue_or_client,
            shared_state=shared_state,
            config=config_manager,
            process_name=process_name,
        )

        target_func(ctx)

    except KeyboardInterrupt:
        logger.info(f"⚠️ {process_name} 收到中断信号")
    except Exception as e:
        logger.error(f"💥 {process_name} 进程崩溃: {e}", exc_info=True)
    finally:
        logger.info(f"🛑 {process_name} 进程退出")


# ==================== 进程入口函数 ====================

def run_camera(ctx: ProcessContext):
    """视频采集进程入口"""
    from modules.camera import CameraProcess
    camera = CameraProcess(ctx)
    camera.run()


def run_ai_detector(ctx: ProcessContext):
    """AI 检测进程入口"""
    from modules.detector import AIDetectorProcess
    detector = AIDetectorProcess(ctx)
    detector.run()


def run_audio_processor(ctx: ProcessContext):
    """音频处理进程入口"""
    from modules.audio import AudioProcess
    audio = AudioProcess(ctx)
    audio.run()


def run_mqtt_client(ctx: ProcessContext):
    """MQTT 通信进程入口"""
    from modules.mqtt.process import MQTTClientProcess
    mqtt_client = MQTTClientProcess(ctx)
    mqtt_client.run()


def run_stream_manager(ctx: ProcessContext):
    """流媒体进程入口"""
    from modules.stream import StreamManagerProcess
    stream = StreamManagerProcess(ctx)
    stream.run()


def run_device_controller(ctx: ProcessContext):
    """硬件控制进程入口"""
    from modules.device import DeviceControllerProcess
    device = DeviceControllerProcess(ctx)
    device.run()


def run_recorder(ctx: ProcessContext):
    """录像进程入口"""
    from modules.recorder import RecorderProcess
    recorder = RecorderProcess(ctx)
    recorder.run()


# ==================== 进程配置生成 ====================

def create_process_configs(config_manager: 'ConfigManager') -> List[ProcessConfig]:
    """
    根据配置文件创建进程配置列表
    
    Args:
        config_manager: ConfigManager 实例
        
    Returns:
        进程配置列表
    """
    delays = config_manager.supervisor.startup_delays
    
    return [
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
        ProcessConfig(
            name='recorder',
            target=run_recorder,
            critical=False,
            startup_delay=delays.get('recorder', 3.0)
        ),
    ]
