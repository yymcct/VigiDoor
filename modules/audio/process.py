"""
音频处理进程
负责音频采集、异常检测和远程喊话
"""

import time
from utils.logger import setup_logger
from core.ipc import IPCClient, MessageType
from core.ipc.registry import ProcessName

from .capture import AudioCaptureManager
from .volume_monitor import VolumeMonitor
from .detector import AudioAnomalyDetector
from .player import AudioPlayer

logger = setup_logger('audio_process')


class AudioProcess:
    """
    音频处理进程 - 负责音频采集、异常检测和远程喊话
    
    架构：三线程模型
    ┌─────────────────────────────────────────┐
    │  主线程（AudioProcess）                  │
    │  - IPC 消息处理                          │
    │  - 生命周期管理                          │
    │  - 心跳发送                              │
    └──────────────┬──────────────────────────┘
                   │
           ┌───────┴────────┐
           ↓                ↓
    ┌──────────────┐  ┌──────────────────────┐
    │ 采集线程      │  │ 播放线程              │
    │ - 实时录音    │  │ - 远程喊话            │
    │ - 音量检测    │  │ - 异步播放            │
    │ - 触发分类    │  └──────────────────────┘
    └──────┬───────┘
           │
           ↓ (音量超阈值)
    ┌──────────────────────┐
    │  YamNet 分类器        │
    │  - 异步推理           │
    │  - 事件上报           │
    └──────────────────────┘
    
    功能：
    1. 从麦克风采集音频
    2. 实时监控音量，超过阈值时触发 YamNet 检测
    3. 检测异常声音（玻璃破碎、呼救声、警报声等）
    4. 播放远程喊话音频
    """
    
    def __init__(self, ipc_client: IPCClient, shared_state, config):
        self.ipc = ipc_client
        self.state = shared_state
        self.config = config
        self.running = True
        
        # 音频配置
        audio_config = config.get('audio', {})
        self.sample_rate = audio_config.get('sample_rate', 16000)
        self.channels = audio_config.get('channels', 1)
        self.device_index = audio_config.get('device_index', None)
        
        # 检测配置
        detector_config = audio_config.get('detector', {})
        self.volume_threshold_db = detector_config.get('volume_threshold_db', 55.0)
        self.debounce_seconds = detector_config.get('debounce_seconds', 2.0)
        self.confidence_threshold = detector_config.get('confidence_threshold', 0.4)
        self.model_path = detector_config.get('model_path', 'models/yamnet.tflite')
        self.enable_dog_bark = detector_config.get('enable_dog_bark', False)
        
        # 组件（延迟初始化）
        self.capture_manager = None
        self.volume_monitor = None
        self.detector = None
        self.player = None
        
        logger.info(f"音频处理进程初始化完成")
        logger.info(f"  采样率: {self.sample_rate} Hz")
        logger.info(f"  声道数: {self.channels}")
        logger.info(f"  音量阈值: {self.volume_threshold_db} dB")
        logger.info(f"  置信度阈值: {self.confidence_threshold}")
    
    def run(self):
        """主循环"""
        logger.info("🎤 音频处理进程启动")
        
        try:
            # 1. 初始化组件
            if not self._initialize_components():
                logger.error("组件初始化失败，进入空闲模式")
                self._run_idle_mode()
                return
            
            # 2. 启动所有线程
            if not self._start_all_threads():
                logger.error("启动线程失败")
                self._cleanup()
                return
            
            # 3. 主循环：处理 IPC 消息和心跳
            last_heartbeat = time.time()
            last_stats_print = time.time()
            
            while self.running:
                # 处理消息
                msg = self.ipc.receive(timeout=1.0)
                if msg:
                    self._handle_message(msg)
                
                # 定期发送心跳
                if time.time() - last_heartbeat > 10:
                    self.ipc.send_heartbeat()
                    last_heartbeat = time.time()
                
                # 定期打印统计信息
                if time.time() - last_stats_print > 60:
                    self._print_statistics()
                    last_stats_print = time.time()
                
        except KeyboardInterrupt:
            logger.info("检测到中断信号")
        except Exception as e:
            logger.error(f"主循环异常: {e}", exc_info=True)
        finally:
            self._cleanup()
            logger.info("音频处理进程退出")
    
    def _initialize_components(self) -> bool:
        """初始化所有组件"""
        try:
            # 1. 初始化音频采集管理器
            self.capture_manager = AudioCaptureManager(
                sample_rate=self.sample_rate,
                channels=self.channels,
                device_index=self.device_index
            )
            
            # 2. 初始化音量监控器
            self.volume_monitor = VolumeMonitor(
                threshold_db=self.volume_threshold_db,
                debounce_seconds=self.debounce_seconds
            )
            
            # 3. 初始化音频检测器
            self.detector = AudioAnomalyDetector(
                model_path=self.model_path,
                confidence_threshold=self.confidence_threshold,
                enable_dog_bark=self.enable_dog_bark
            )
            
            # 加载 YamNet 模型
            if not self.detector.initialize():
                logger.warning("YamNet 模型加载失败，将无法进行音频检测")
                # 继续运行，但不启动检测线程
            
            # 4. 初始化音频播放器
            self.player = AudioPlayer()
            
            # 5. 注册回调
            self.capture_manager.register_callback(self._on_audio_chunk)
            self.detector.on_anomaly_detected = self._on_anomaly_detected
            
            logger.info("✅ 所有组件初始化完成")
            return True
            
        except Exception as e:
            logger.error(f"组件初始化失败: {e}", exc_info=True)
            return False
    
    def _start_all_threads(self) -> bool:
        """启动所有线程"""
        try:
            if not self.capture_manager.start():
                logger.error("启动音频采集失败")
                return False
            
            if self.detector.yamnet.interpreter is not None:
                if not self.detector.start():
                    logger.warning("启动音频检测失败")
            else:
                logger.warning("跳过音频检测线程（模型未加载）")
            
            if not self.player.start():
                logger.warning("启动音频播放失败")
            
            logger.info("✅ 所有线程已启动")
            return True
            
        except Exception as e:
            logger.error(f"启动线程失败: {e}", exc_info=True)
            return False
    
    def _on_audio_chunk(self, audio_chunk):
        """音频块回调：进行音量检测"""
        try:
            # 音量监控
            should_detect, db_value = self.volume_monitor.analyze(audio_chunk)
            
            if should_detect:
                logger.info(f"🔊 音量触发检测: {db_value:.1f} dB")
                
                # 获取最近 1 秒的音频进行检测
                audio_window = self.capture_manager.get_buffer_window(duration=1.0)
                
                if audio_window is not None:
                    # 异步检测
                    self.detector.detect(audio_window)
                
        except Exception as e:
            logger.error(f"音频块处理异常: {e}")
    
    def _on_anomaly_detected(self, result: dict):
        """异常检测回调：上报到 Supervisor"""
        try:
            logger.warning(f"🚨 检测到音频异常: {result['event_name']}")
            
            # 发送异常事件消息
            self.ipc.send(
                msg_type=MessageType.AUDIO_ANOMALY,
                target=ProcessName.SUPERVISOR,
                data={
                    'event_type': result['event_type'],
                    'event_name': result['event_name'],
                    'confidence': result['confidence'],
                    'timestamp': result['timestamp'],
                    'inference_time_ms': result['inference_time_ms']
                }
            )
            
        except Exception as e:
            logger.error(f"上报异常失败: {e}")
    
    def _handle_message(self, msg):
        """处理 IPC 消息"""
        msg_dict = msg.to_dict()
        msg_type = msg_dict.get('type')
        msg_data = msg_dict.get('data', {})
        
        if msg_type == MessageType.CMD_PLAY_AUDIO.value or msg_type == 'play_audio':
            logger.info("🔊 收到远程喊话指令")
            self._handle_play_audio(msg_data)
        
        elif msg_type == MessageType.SHUTDOWN.value:
            logger.info("收到关闭信号")
            self.running = False
    
    def _handle_play_audio(self, data: dict):
        """处理播放音频指令"""
        try:
            # 解析音频路径
            audio_path = data.get('path') or data.get('file') or data.get('audio_path')
            
            if not audio_path:
                logger.error("音频路径为空")
                return
            
            # 加入播放队列
            if self.player:
                self.player.play(audio_path)
            else:
                logger.error("播放器未初始化")
                
        except Exception as e:
            logger.error(f"播放音频失败: {e}")
    
    def _print_statistics(self):
        """打印统计信息"""
        try:
            logger.info("=== 音频处理统计 ===")
            
            # 音量监控统计
            if self.volume_monitor:
                stats = self.volume_monitor.get_statistics()
                logger.info(f"音量检查: {stats['total_checks']} 次")
                logger.info(f"触发检测: {stats['trigger_count']} 次 ({stats['trigger_rate']})")
            
            # 异常检测统计
            if self.detector and self.detector.yamnet.interpreter:
                stats = self.detector.get_statistics()
                logger.info(f"YamNet 检测: {stats['total_detections']} 次")
                logger.info(f"异常事件: {stats['anomaly_count']} 次 ({stats['anomaly_rate']})")
            
            # 播放统计
            if self.player:
                stats = self.player.get_statistics()
                logger.info(f"音频播放: {stats['total_plays']} 次")
                logger.info(f"播放成功率: {stats['success_rate']}")
            
            logger.info("==================")
            
        except Exception as e:
            logger.error(f"打印统计信息失败: {e}")
    
    def _run_idle_mode(self):
        """空闲模式：仅发送心跳"""
        logger.info("进入空闲模式（仅心跳）")
        
        while self.running:
            self.ipc.send_heartbeat()
            time.sleep(10)
    
    def _cleanup(self):
        """清理资源"""
        logger.info("正在清理资源...")
        
        try:
            if self.capture_manager:
                self.capture_manager.stop()
            
            if self.detector:
                self.detector.stop()
            
            if self.player:
                self.player.stop()
                
        except Exception as e:
            logger.error(f"清理资源失败: {e}")
        
        logger.info("✅ 资源清理完成")
