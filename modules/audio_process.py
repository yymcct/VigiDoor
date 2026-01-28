"""
音频处理进程
负责音频采集、异常检测和远程喊话
"""

import time
from utils.logger import setup_logger
from core.ipc import IPCClient, MessageType
from core.ipc.registry import ProcessName

logger = setup_logger('audio_processor')


class AudioProcessorProcess:
    """
    音频处理进程 - 负责音频采集、异常检测和远程喊话
    
    功能：
    1. 从麦克风采集音频
    2. 检测异常声音（如破窗、尖叫）
    3. 播放远程喊话音频
    """
    
    def __init__(self, ipc_client: IPCClient, shared_state, config):
        self.ipc = ipc_client
        self.state = shared_state
        self.config = config
        self.running = True
        
        # 音频配置
        self.sample_rate = config['audio']['sample_rate']
        self.channels = config['audio']['channels']
        self.chunk_size = config['audio']['chunk_size']
        
        logger.info(f"音频处理进程初始化完成")
        logger.info(f"  采样率: {self.sample_rate} Hz")
        logger.info(f"  声道数: {self.channels}")
    
    def run(self):
        """主循环"""
        logger.info("🎤 音频处理进程启动")
        
        # 初始化音频设备
        audio_device = self._init_audio()
        if not audio_device:
            logger.error("音频设备初始化失败，进入模拟模式")
            self._run_simulation_mode()
            return
        
        last_heartbeat = time.time()
        
        try:
            while self.running:
                # 采集音频（初版模拟）
                audio_data = self._capture_audio_simulation()
                
                # 检测异常声音（初版模拟）
                is_anomaly = self._detect_audio_anomaly_simulation()
                
                if is_anomaly:
                    self._report_audio_anomaly()
                
                # 处理消息
                msg = self.ipc.receive(timeout=0.1)
                if msg:
                    msg_dict = msg.to_dict() if hasattr(msg, 'to_dict') else msg
                    msg_type = msg_dict.get('type')
                    
                    if msg_type == 'play_audio' or msg_type == MessageType.CMD_PLAY_AUDIO.value:
                        logger.info("🔊 收到远程喊话指令")
                        self._play_audio(msg_dict.get('data'))
                    
                    elif msg_type == 'shutdown' or msg_type == MessageType.SHUTDOWN.value:
                        logger.info("收到关闭信号")
                        break
                
                # 定期发送心跳
                if time.time() - last_heartbeat > 10:
                    self.ipc.send_heartbeat()
                    last_heartbeat = time.time()
                
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            logger.info("检测到中断信号")
        finally:
            self._cleanup(audio_device)
            logger.info("音频处理进程退出")
    
    def _init_audio(self):
        """初始化音频设备"""
        try:
            # 尝试初始化 PyAudio
            # import pyaudio
            # p = pyaudio.PyAudio()
            # stream = p.open(
            #     format=pyaudio.paInt16,
            #     channels=self.channels,
            #     rate=self.sample_rate,
            #     input=True,
            #     frames_per_buffer=self.chunk_size
            # )
            # logger.info("✅ 音频设备初始化成功")
            # return stream
            
            # 初版返回模拟对象
            logger.info("✅ 音频设备初始化成功（模拟模式）")
            return {'mode': 'simulation'}
            
        except Exception as e:
            logger.error(f"音频设备初始化失败: {e}")
            return None
    
    def _capture_audio_simulation(self):
        """采集音频（模拟）"""
        return None
    
    def _detect_audio_anomaly_simulation(self):
        """检测异常声音（模拟）"""
        # 初版：永不触发
        return False
    
    def _report_audio_anomaly(self):
        """上报音频异常"""
        logger.warning("🔊 检测到异常声音")
        
        self.ipc.send(
            msg_type=MessageType.AUDIO_ANOMALY,
            target=ProcessName.SUPERVISOR,
            data={
                'event_type': 'audio_anomaly',
                'timestamp': time.time()
            }
        )
    
    def _play_audio(self, audio_data):
        """播放音频（远程喊话）"""
        try:
            logger.info("🔊 播放远程喊话音频")
            
            # 真实实现：
            # 1. 从 audio_data 解析音频 URL 或 base64
            # 2. 下载音频文件
            # 3. 使用 PyAudio 或 aplay 播放
            
            # 初版模拟
            logger.info("  [模拟] 播放音频中...")
            time.sleep(2)
            logger.info("  [模拟] 播放完成")
            
        except Exception as e:
            logger.error(f"播放音频失败: {e}")
    
    def _run_simulation_mode(self):
        """模拟模式运行"""
        logger.info("进入模拟模式")
        
        while self.running:
            # 定期发送心跳
            self.ipc.send_heartbeat()
            time.sleep(10)
    
    def _cleanup(self, audio_device):
        """清理资源"""
        try:
            if audio_device and audio_device.get('mode') != 'simulation':
                # audio_device.stop_stream()
                # audio_device.close()
                pass
        except:
            pass
