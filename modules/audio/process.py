"""
音频处理进程
负责音频采集、音量异常检测和远程喊话
"""

import time
from core.process_context import ProcessContext
from utils.logger import setup_logger
from utils.config import ConfigManager
from core.ipc import IPCClient, MessageType
from core.ipc.registry import ProcessName
from core.state import StateKey

from .capture import AudioCaptureManager
from .baseline_monitor import EnvironmentBaselineMonitor
from .volume_monitor import VolumeAnomalyDetector, AlarmLevel
from .detector import AudioAnomalyDetector
from .player import AudioPlayer
from .remote_call import RemoteCallClient
from .stream_player import StreamAudioPlayer

logger = setup_logger('audio_process')


class AudioProcess:
    """
    音频处理进程 - 负责音频采集、音量异常检测和远程喊话
    
    架构：三线程模型 + 环境自适应检测
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
    │ - 基线学习    │  │ - 异步播放            │
    │ - 音量突变检测│  └──────────────────────┘
    └──────┬───────┘
           │
           ↓ (音量突变)
    ┌──────────────────────┐
    │  YamNet 分类器 (可选) │
    │  - 仅记录日志         │
    │  - 用于模型训练       │
    └──────────────────────┘
    
    功能：
    1. 从麦克风采集音频
    2. 学习环境噪音基线（动态适应）
    3. 检测音量突变（相对基线）
    4. 触发报警（多级阈值）
    5. 播放远程喊话音频
    6. （可选）YamNet辅助记录
    """
    
    def __init__(self, ctx: 'ProcessContext'):
        self.ipc = ctx.ipc
        self.state = ctx.shared_state
        self.config_manager = ctx.config
        self.running = True
        
        # 音频配置 - 使用强类型访问
        audio_config = self.config_manager.audio
        
        # 基线学习配置
        self.learning_window_minutes = audio_config.baseline_learning_window_minutes
        self.update_window_seconds = audio_config.baseline_update_window_seconds
        self.outlier_threshold_iqr = audio_config.baseline_outlier_threshold_iqr
        self.update_alpha = audio_config.baseline_update_alpha
        
        # 音量突变检测配置
        self.alert_threshold_db = audio_config.anomaly_alert_threshold_db
        self.alarm_threshold_db = audio_config.anomaly_alarm_threshold_db
        self.duration_threshold = audio_config.anomaly_duration_threshold_seconds
        self.cooldown_seconds = audio_config.anomaly_cooldown_seconds
        
        # YamNet 配置（可选）
        self.yamnet_enabled = audio_config.yamnet_enabled
        self.yamnet_model_path = audio_config.yamnet_model_path
        self.yamnet_confidence = audio_config.yamnet_confidence_threshold
        
        # 组件（延迟初始化）
        self.capture_manager = None
        self.baseline_monitor = None
        self.anomaly_detector = None
        self.yamnet_detector = None
        self.player = None
        self.remote_call = None
        self.stream_player = None
        
        logger.info(f"音频处理进程初始化完成")
        logger.info(f"  基线学习窗口: {self.learning_window_minutes} 分钟")
        logger.info(f"  警戒阈值: +{self.alert_threshold_db} dB")
        logger.info(f"  报警阈值: +{self.alarm_threshold_db} dB")
        logger.info(f"  YamNet辅助: {'启用' if self.yamnet_enabled else '禁用'}")
    
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
            self.capture_manager = AudioCaptureManager()
            
            # 2. 初始化环境基线学习器
            self.baseline_monitor = EnvironmentBaselineMonitor(
                learning_window_minutes=self.learning_window_minutes,
                update_window_seconds=self.update_window_seconds,
                outlier_threshold_iqr=self.outlier_threshold_iqr,
                update_alpha=self.update_alpha
            )
            
            # 3. 初始化音量突变检测器
            self.anomaly_detector = VolumeAnomalyDetector(
                alert_threshold_db=self.alert_threshold_db,
                alarm_threshold_db=self.alarm_threshold_db,
                duration_threshold_seconds=self.duration_threshold,
                cooldown_seconds=self.cooldown_seconds
            )
            
            # 4. 初始化YamNet检测器（可选）
            if self.yamnet_enabled:
                self.yamnet_detector = AudioAnomalyDetector(
                    model_path=self.yamnet_model_path,
                    confidence_threshold=self.yamnet_confidence,
                    enable_dog_bark=False,
                    enable_alarm=False  # 仅辅助记录，不触发报警
                )
                
                # 加载 YamNet 模型
                if not self.yamnet_detector.initialize():
                    logger.warning("YamNet 模型加载失败，禁用 YamNet 辅助功能")
                    self.yamnet_detector = None
                else:
                    logger.info("✅ YamNet 辅助功能启用")
            else:
                logger.info("YamNet 辅助功能已禁用")
            
            # 5. 初始化音频播放器
            self.player = AudioPlayer()

            # 6. 初始化远程喊话组件
            self.stream_player = StreamAudioPlayer(sample_rate=16000, channels=1, max_frame_size=320)
            self.remote_call = RemoteCallClient(on_audio_packet=self._handle_call_audio)
            
            # 7. 注册回调
            self.capture_manager.register_callback(self._on_audio_chunk)
            
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
            
            # YamNet 线程（可选）
            if self.yamnet_detector:
                if not self.yamnet_detector.start():
                    logger.warning("启动 YamNet 辅助功能失败")
                    self.yamnet_detector = None
            
            if not self.player.start():
                logger.warning("启动音频播放失败")
            
            logger.info("✅ 所有线程已启动")
            return True
            
        except Exception as e:
            logger.error(f"启动线程失败: {e}", exc_info=True)
            return False
    
    def _on_audio_chunk(self, audio_chunk):
        """音频块回调：基线学习 + 音量突变检测"""
        try:
            # 验证输入
            if audio_chunk is None or not hasattr(audio_chunk, '__len__') or len(audio_chunk) == 0:
                logger.debug("收到无效的音频块，跳过处理")
                return
            
            # 1. 计算当前音量（dB）
            current_db = self.anomaly_detector._calculate_db(audio_chunk)
            
            # 2. 添加样本到基线学习器
            self.baseline_monitor.add_sample(current_db)
            
            # 3. 获取基线信息
            baseline_info = self.baseline_monitor.get_baseline_info()
            baseline_db = baseline_info['baseline_db']
            
            # 基线学习期间，跳过检测
            if baseline_db is None:
                #logger.debug(f"基线学习中... 当前音量: {current_db:.1f}dB")
                return

            # 撤防状态：继续更新基线，但不触发报警
            if not self.state.get(StateKey.IS_ARMED, True):
                return

            # 4. 音量突变检测
            result = self.anomaly_detector.analyze(audio_chunk, baseline_db)
            if result is None:
                logger.warning("音量突变检测返回 None，跳过处理")
                return
            
            alarm_level, current_db, delta_db = result
            
            # 5. 根据报警级别处理
            if alarm_level == AlarmLevel.ALARM:
                # 触发报警
                self._trigger_alarm(current_db, baseline_db, delta_db)
                
                # 通知基线学习器进入报警状态（暂停更新基线）
                self.baseline_monitor.set_alarm_state(True)
                
                # （可选）触发 YamNet 辅助检测
                if self.yamnet_detector:
                    audio_window = self.capture_manager.get_buffer_window(duration=1.0)
                    if audio_window is not None:
                        self.yamnet_detector.detect(audio_window)
            
            elif alarm_level == AlarmLevel.ALERT:
                # 警戒状态：仅记录
                logger.debug(f"⚠️  警戒: {current_db:.1f}dB (Δ{delta_db:+.1f}dB)")
            
            else:
                # 正常状态：解除报警
                if self.baseline_monitor.is_alarm_active:
                    self.baseline_monitor.set_alarm_state(False)
                    
        except Exception as e:
            logger.error(f"音频块处理异常: {e}")
    
    def _trigger_alarm(self, current_db: float, baseline_db: float, delta_db: float):
        """触发音量报警"""
        try:
            logger.warning(f"🚨 音量报警: {current_db:.1f}dB (基线: {baseline_db:.1f}dB, 偏差: {delta_db:+.1f}dB)")
            
            # 发送报警消息到 Supervisor
            self.ipc.send(
                msg_type=MessageType.AUDIO_ANOMALY,
                target=ProcessName.SUPERVISOR,
                data={
                    'event_type': 'volume_anomaly',
                    'event_name': '音量突变异常',
                    'current_db': current_db,
                    'baseline_db': baseline_db,
                    'delta_db': delta_db,
                    'timestamp': time.time()
                }
            )
            
        except Exception as e:
            logger.error(f"触发报警失败: {e}")
    
    def _handle_message(self, msg):
        """处理 IPC 消息"""
        msg_dict = msg.to_dict()
        msg_type = msg_dict.get('type')
        msg_data = msg_dict.get('data', {})
        
        if msg_type == MessageType.CMD_PLAY_AUDIO.value:
            logger.info("🔊 收到远程喊话指令")
            self._handle_play_audio(msg_data)

        elif msg_type == MessageType.CMD_INITIATE_CALL.value:
            logger.info("📞 收到远程喊话建立指令")
            self._handle_initiate_call(msg_data)

        elif msg_type == MessageType.CMD_TERMINATE_CALL.value:
            logger.info("📞 收到远程喊话结束指令")
            self._handle_terminate_call()
        
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

    def _handle_initiate_call(self, data: dict):
        """处理建立远程喊话"""
        websocket_url = data.get('websocket_url')
        device_id = self.config_manager.device.id

        if not self.stream_player:
            logger.error("远程喊话播放器未初始化")
            return

        if not self.stream_player.start():
            logger.error("远程喊话播放器启动失败")
            return

        if not self.remote_call:
            logger.error("远程喊话客户端未初始化")
            self.stream_player.stop()
            return

        if not self.remote_call.connect(websocket_url, device_id=device_id):
            self.stream_player.stop()

    def _handle_terminate_call(self):
        """处理结束远程喊话"""
        if self.remote_call:
            self.remote_call.disconnect()
        if self.stream_player:
            self.stream_player.stop()

    def _handle_call_audio(self, audio_packet: bytes):
        """处理远程喊话音频包"""
        if not self.stream_player:
            return
        self.stream_player.enqueue_opus(audio_packet)
    
    def _print_statistics(self):
        """打印统计信息"""
        try:
            logger.info("=== 音频处理统计 ===")
            
            # 基线学习统计
            if self.baseline_monitor:
                info = self.baseline_monitor.get_baseline_info()
                status = "就绪" if info['is_ready'] else "学习中"
                logger.info(f"基线状态: {status}")
                if info['baseline_db']:
                    logger.info(f"  基线音量: {info['baseline_db']:.1f} dB")
                    logger.info(f"  标准差: {info['baseline_std']:.1f} dB")
                logger.info(f"  样本数: {info['sample_count']}")
                logger.info(f"  更新次数: {info['update_count']}")
            
            # 音量突变统计
            if self.anomaly_detector:
                stats = self.anomaly_detector.get_statistics()
                logger.info(f"音量检查: {stats['total_checks']} 次")
                logger.info(f"警戒次数: {stats['alert_count']} 次 ({stats['alert_rate']})")
                logger.info(f"报警次数: {stats['alarm_count']} 次 ({stats['alarm_rate']})")
            
            # YamNet 统计（如果启用）
            if self.yamnet_detector:
                stats = self.yamnet_detector.get_statistics()
                logger.info(f"YamNet 检测: {stats['total_detections']} 次")
                logger.info(f"异常识别: {stats['anomaly_count']} 次")
            
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
            
            if self.yamnet_detector:
                self.yamnet_detector.stop()
            
            if self.player:
                self.player.stop()

            if self.remote_call:
                self.remote_call.disconnect()

            if self.stream_player:
                self.stream_player.stop()
                
        except Exception as e:
            logger.error(f"清理资源失败: {e}")
        
        logger.info("✅ 资源清理完成")
