"""
流媒体管理进程（重构版）
采用双线程架构：OSD渲染 + FFmpeg编码推流
"""

import time
import subprocess
import threading
import queue
from datetime import datetime
from enum import Enum
import numpy as np
from utils.logger import setup_logger
from core.ipc import IPCClient, MessageType
from core.ipc.registry import ProcessName
from utils.frame_buffer import SharedFrameBuffer

logger = setup_logger('stream_manager')


class StreamState(Enum):
    """推流状态机"""
    IDLE = "idle"            # 空闲
    STARTING = "starting"    # 启动中
    STREAMING = "streaming"  # 推流中
    STOPPING = "stopping"    # 停止中


class StreamManagerProcess:
    """
    流媒体管理进程
    
    架构：
    ┌───────────────────────────────────────┐
    │  主控线程                              │
    │  - 监听MQTT开始/停止推流指令           │
    │  - 管理子线程生命周期                  │
    └───────────────────────────────────────┘
                  ↓
    ┌─────────────┬──────────────────────────┐
    │  线程1       │  线程2                    │
    │  OSD渲染     │  编码+RTSP/RTMP推流       │
    └─────────────┴──────────────────────────┘
    
    功能：
    1. 从共享内存读取原始帧
    2. OSD叠加（时间戳、检测框、警戒线）
    3. 软件编码为H.264
    4. 推流到ZLMediaKit（RTSP/RTMP）
    """
    
    def __init__(self, ipc_client: IPCClient, shared_state, config):
        self.ipc = ipc_client
        self.state = shared_state
        self.config = config
        self.running = True
        
        # 推流配置
        self.zlm_server = config['stream']['zlm_server']
        self.stream_key = config['stream']['stream_key'].format(
            device_id=config['device']['id']
        )
        self.bitrate = config['stream']['bitrate']
        
        # 状态机
        self.stream_state = StreamState.IDLE
        
        # 共享内存帧缓冲（读取者）
        self.frame_buffer = None
        
        # 线程间队列
        self.osd_queue = queue.Queue(maxsize=5)      # OSD渲染 → 编码推流
        
        # 子线程
        self.osd_thread = None
        self.encode_stream_thread = None  # 合并编码和推流
        
        # 最新检测结果（用于OSD）
        self.latest_detections = []
        self.detection_lock = threading.Lock()
        
        # 帧就绪通知（消息驱动，替代轮询）
        self.frame_ready_event = threading.Event()
        self.latest_frame_id = -1
        self.frame_id_lock = threading.Lock()
        
        # 组合完整推流URL
        self.stream_url = f"{self.zlm_server}/{self.stream_key}"
        
        logger.info(f"流媒体管理进程初始化完成（重构版）")
        logger.info(f"  设备ID: {config['device']['id']}")
        logger.info(f"  推流地址: {self.stream_url}")
    
    def run(self):
        """主循环"""
        logger.info("📹 流媒体管理进程启动（重构版）")
        
        last_heartbeat = time.time()
        
        try:
            while self.running:
                # 处理消息
                msg = self.ipc.receive(timeout=1.0)
                if msg:
                    # 直接访问IPCMessage对象属性
                    msg_dict = msg.to_dict()
                    msg_type = msg_dict.get('type')
                    msg_data = msg_dict.get('data', {})
                    
                    if msg_type == 'start_stream':
                        logger.info("📤 收到开始推流指令")
                        self._start_stream()
                    
                    elif msg_type == 'stop_stream':
                        logger.info("⏹️  收到停止推流指令")
                        self._stop_stream()
                    
                    elif msg_type == 'detection_result':
                        # 接收AI检测结果（用于OSD渲染）
                        self._update_detection_result(msg_data)
                    
                    elif msg_type == 'frame_ready' or msg_type == MessageType.FRAME_READY.value:
                        # 接收新帧就绪通知（消息驱动，避免轮询）
                        self._on_frame_ready(msg_data)
                    
                    elif msg_type == 'shutdown':
                        logger.info("收到关闭信号")
                        break
                
                # 定期发送心跳
                if time.time() - last_heartbeat > 10:
                    self.ipc.send_heartbeat()
                    last_heartbeat = time.time()
                
        except KeyboardInterrupt:
            logger.info("检测到中断信号")
        finally:
            self._stop_stream()
            logger.info("流媒体管理进程退出")
    
    def _update_detection_result(self, data):
        """更新检测结果（用于OSD渲染）"""
        with self.detection_lock:
            self.latest_detections = data.get('detections', [])
    
    def _on_frame_ready(self, data):
        """处理新帧就绪通知（消息驱动）"""
        frame_id = data.get('frame_id', -1)
        with self.frame_id_lock:
            self.latest_frame_id = frame_id
        # 通知OSD渲染线程有新帧
        self.frame_ready_event.set()
    
    def _start_stream(self):
        """启动推流"""
        if self.stream_state != StreamState.IDLE:
            logger.warning(f"当前状态 {self.stream_state.value}，无法启动推流")
            return
        
        try:
            self.stream_state = StreamState.STARTING
            logger.info("开始启动推流...")
            
            # 1. 连接共享内存
            self._init_shared_memory()
            
            # 2. 启动OSD渲染线程
            self.osd_thread = threading.Thread(
                target=self._osd_render_loop,
                name="OSD-Render",
                daemon=True
            )
            self.osd_thread.start()
            logger.info("✅ OSD渲染线程已启动")
            
            # 3. 启动编码推流线程（合并）
            self.encode_stream_thread = threading.Thread(
                target=self._encode_and_stream_loop,
                name="Encode-Stream",
                daemon=True
            )
            self.encode_stream_thread.start()
            logger.info("✅ 编码推流线程已启动")
            
            # 更新状态
            self.stream_state = StreamState.STREAMING
            self.state['is_streaming'] = True
            logger.info("✅ 推流已启动")
            
        except Exception as e:
            logger.error(f"启动推流失败: {e}", exc_info=True)
            self.stream_state = StreamState.IDLE
            self._cleanup_threads()
    
    def _stop_stream(self):
        """停止推流"""
        if self.stream_state == StreamState.IDLE:
            return
        
        try:
            logger.info("停止推流...")
            self.stream_state = StreamState.STOPPING
            
            # 停止所有线程
            self._cleanup_threads()
            
            # 关闭共享内存
            if self.frame_buffer:
                self.frame_buffer.close()
                self.frame_buffer = None
            
            # 更新状态
            self.stream_state = StreamState.IDLE
            self.state['is_streaming'] = False
            logger.info("✅ 推流已停止")
            
        except Exception as e:
            logger.error(f"停止推流失败: {e}")
    
    def _init_shared_memory(self):
        """初始化共享内存（读取者模式）"""
        try:
            # 等待共享内存创建
            max_wait = 10
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                try:
                    self.frame_buffer = SharedFrameBuffer(
                        width=self.config['camera']['width'],
                        height=self.config['camera']['height'],
                        name=self.config['camera']['shared_memory_name'],
                        create=False
                    )
                    logger.info("✅ 共享内存连接成功")
                    return
                except FileNotFoundError:
                    logger.warning("等待共享内存创建...")
                    time.sleep(1)
            
            raise RuntimeError("共享内存连接超时")
            
        except Exception as e:
            logger.error(f"共享内存连接失败: {e}")
            raise
    
    # ==================== 线程1：OSD渲染 ====================
    
    def _osd_render_loop(self):
        """OSD渲染线程 - 叠加时间戳和检测框（事件驱动优化）"""
        logger.info("🎨 OSD渲染线程启动（事件驱动模式）")
        
        last_frame_id = -1
        
        try:
            import cv2
            
            while self.stream_state in [StreamState.STARTING, StreamState.STREAMING]:
                try:
                    # 等待新帧就绪通知（事件驱动，避免CPU轮询）
                    if not self.frame_ready_event.wait(timeout=1.0):
                        continue
                    
                    self.frame_ready_event.clear()
                    
                    # 读取最新帧
                    frame_data = self.frame_buffer.read_frame(copy=True)
                    
                    if frame_data is None:
                        continue
                    
                    frame, frame_id, timestamp = frame_data
                    
                    # 避免重复处理（检查是否是新帧）
                    if frame_id <= last_frame_id:
                        continue
                    
                    last_frame_id = frame_id
                    
                    # OSD叠加
                    frame_with_osd = self._render_osd(frame, timestamp)
                    
                    # 放入编码队列（非阻塞，队列满则丢帧）
                    try:
                        self.osd_queue.put_nowait((frame_with_osd, frame_id, timestamp))
                    except queue.Full:
                        logger.debug("OSD队列已满，丢弃帧")
                    
                except Exception as e:
                    logger.error(f"OSD渲染异常: {e}")
                    time.sleep(0.1)
                    
        except Exception as e:
            logger.error(f"OSD渲染线程崩溃: {e}", exc_info=True)
        finally:
            logger.info("OSD渲染线程退出")
    
    def _render_osd(self, frame, timestamp):
        """渲染OSD叠加"""
        import cv2
        
        # 复制帧（避免修改原始数据）
        frame_osd = frame.copy()
        
        # 1. 渲染时间戳
        time_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
        cv2.putText(
            frame_osd, time_str, (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2
        )
        
        # 2. 渲染设备信息
        device_id = self.config['device']['id']
        cv2.putText(
            frame_osd, f"Device: {device_id}", (20, frame.shape[0] - 20),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1
        )
        
        # 3. 渲染检测框
        with self.detection_lock:
            detections = self.latest_detections.copy()
        
        height, width = frame.shape[:2]
        
        for det in detections:
            # 归一化坐标 → 像素坐标
            x, y, w, h = det['bbox']
            x1 = int(x * width)
            y1 = int(y * height)
            x2 = int((x + w) * width)
            y2 = int((y + h) * height)
            
            # 根据系统状态选择颜色
            state = self.state.get('global_state', 'safe')
            if state == 'alarm':
                color = (0, 0, 255)  # 红色
            elif state == 'alert':
                color = (0, 255, 255)  # 黄色
            else:
                color = (0, 255, 0)  # 绿色
            
            # 绘制矩形
            cv2.rectangle(frame_osd, (x1, y1), (x2, y2), color, 2)
            
            # 绘制标签
            label = f"{det['class_name']} {det['confidence']:.2f}"
            cv2.putText(
                frame_osd, label, (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2
            )
        
        return frame_osd
    
    # ==================== 线程2：编码推流 ====================
    
    def _encode_and_stream_loop(self):
        """编码推流线程 - 使用FFmpeg一次性完成编码和推流"""
        logger.info("⚙️📡 编码推流线程启动")
        
        ffmpeg_process = None
        
        try:
            # 启动FFmpeg编码推流进程
            ffmpeg_process = self._start_ffmpeg_encoder_streamer()
            
            if not ffmpeg_process:
                logger.error("FFmpeg编码推流器启动失败")
                return
            
            frame_count = 0
            error_count = 0
            max_errors = 10
            
            while self.stream_state in [StreamState.STARTING, StreamState.STREAMING]:
                try:
                    # 从OSD队列获取帧
                    frame, frame_id, timestamp = self.osd_queue.get(timeout=1.0)
                    
                    # 写入FFmpeg stdin（原始RGB数据）
                    try:
                        ffmpeg_process.stdin.write(frame.tobytes())
                        ffmpeg_process.stdin.flush()
                        frame_count += 1
                        
                        if frame_count % 300 == 0:  # 每10秒记录一次（假设30fps）
                            logger.debug(f"已推流 {frame_count} 帧")
                        
                        error_count = 0  # 重置错误计数
                        
                    except BrokenPipeError:
                        logger.error("FFmpeg进程管道断开")
                        break
                    except IOError as e:
                        logger.error(f"写入FFmpeg失败: {e}")
                        error_count += 1
                        if error_count >= max_errors:
                            logger.error("连续错误过多，退出推流")
                            break
                    
                except queue.Empty:
                    continue
                except Exception as e:
                    logger.error(f"编码推流异常: {e}")
                    time.sleep(0.1)
            
            logger.info(f"编码推流结束，共推送 {frame_count} 帧")
            
        except Exception as e:
            logger.error(f"编码推流线程崩溃: {e}", exc_info=True)
        finally:
            # 清理FFmpeg进程
            if ffmpeg_process:
                try:
                    ffmpeg_process.stdin.close()
                    ffmpeg_process.wait(timeout=5)
                    logger.info("FFmpeg进程正常退出")
                except subprocess.TimeoutExpired:
                    logger.warning("FFmpeg进程未响应，强制终止")
                    ffmpeg_process.kill()
                    ffmpeg_process.wait()
                except Exception as e:
                    logger.error(f"清理FFmpeg进程失败: {e}")
                    try:
                        ffmpeg_process.kill()
                    except:
                        pass
            
            logger.info("编码推流线程退出")
    
    def _start_ffmpeg_encoder_streamer(self):
        """启动FFmpeg编码推流子进程"""
        try:
            width = self.config['camera']['width']
            height = self.config['camera']['height']
            fps = self.config['stream']['fps']
            
            # 使用预先组合好的完整URL
            stream_url = self.stream_url
            
            # 判断是RTSP还是RTMP
            is_rtsp = stream_url.startswith('rtsp://')
            
            # FFmpeg命令（参考用户成功的命令优化）
            cmd = [
                'ffmpeg',
                '-y',  # 覆盖输出
                # 输入配置
                '-f', 'rawvideo',
                '-pixel_format', 'rgb24',
                '-video_size', f'{width}x{height}',
                '-framerate', str(fps),
                '-i', 'pipe:0',  # 从stdin读取
                # 编码配置（软件编码，优化参数）
                '-c:v', 'libx264',
                '-preset', 'ultrafast',      # 最快预设
                '-tune', 'zerolatency',      # 零延迟优化
                '-b:v', self.bitrate,        # 码率
                '-maxrate', self.bitrate,    # 最大码率
                '-bufsize', f'{int(self.bitrate[:-1]) * 2}k',  # 缓冲区大小
                '-g', str(fps * 2),          # GOP大小（2秒）
                '-keyint_min', str(fps),     # 最小关键帧间隔
                '-pix_fmt', 'yuv420p',       # 输出像素格式（Baseline兼容）
                '-profile:v', 'baseline',    # H.264 Baseline profile（兼容性最好）
                '-an',  # 无音频
            ]
            
            # 根据协议添加输出参数
            if is_rtsp:
                cmd.extend([
                    '-f', 'rtsp',
                    '-rtsp_transport', 'tcp',  # 使用TCP传输（更稳定）
                    stream_url
                ])
            else:
                # RTMP/FLV
                cmd.extend([
                    '-f', 'flv',
                    stream_url
                ])
            
            logger.info(f"启动FFmpeg编码推流器")
            logger.info(f"  输入: {width}x{height} @ {fps}fps RGB24")
            logger.info(f"  输出: H.264 @ {self.bitrate}")
            logger.info(f"  推流: {stream_url}")
            
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=10**8  # 100MB缓冲区
            )
            
            # 启动stderr读取线程（避免管道阻塞）
            def read_stderr():
                try:
                    for line in process.stderr:
                        line_str = line.decode('utf-8', errors='ignore').strip()
                        if line_str:
                            # 只记录重要信息
                            if 'error' in line_str.lower() or 'warning' in line_str.lower():
                                logger.warning(f"FFmpeg: {line_str}")
                except:
                    pass
            
            stderr_thread = threading.Thread(target=read_stderr, daemon=True)
            stderr_thread.start()
            
            # 等待一小段时间确保进程启动
            time.sleep(0.5)
            
            if process.poll() is not None:
                raise RuntimeError(f"FFmpeg进程启动后立即退出，返回码: {process.returncode}")
            
            logger.info("✅ FFmpeg编码推流器已启动")
            return process
            
        except Exception as e:
            logger.error(f"启动FFmpeg失败: {e}")
            return None
    
    # ==================== 辅助方法 ====================
    
    def _cleanup_threads(self):
        """清理所有子线程"""
        logger.info("清理子线程...")
        
        # 等待线程退出（最多5秒）
        threads = [self.osd_thread, self.encode_stream_thread]
        for thread in threads:
            if thread and thread.is_alive():
                thread.join(timeout=5)
        
        # 清空队列
        while not self.osd_queue.empty():
            try:
                self.osd_queue.get_nowait()
            except:
                break
        
        logger.info("子线程已清理")
