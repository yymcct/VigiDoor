"""
AI 检测进程
负责视频分析和异常检测
"""

import dataclasses
import time
from utils.logger import setup_logger
from core.ipc import IPCClient, MessageType
from core.ipc.message import create_message
from core.ipc.registry import ProcessName
from core.process_context import ProcessContext

from .frame_reader import FrameReader
from .strategy import DetectionStrategy
from .analyzer import ResultAnalyzer
from .pipeline import DetectionPipeline
from .detectors import create_detector_pipeline

logger = setup_logger('ai_detector')


class AIDetectorProcess:
    """
    AI 检测进程
    
    架构：
        帧读取器 → 检测策略 → Pipeline → 结果分析器 → IPC通信
        
    Pipeline流程：
        1. 运动检测（无运动→早停）
        2. YOLO检测（无人→早停）
        3. 区域检测（判断是否入侵）
    """
    
    def __init__(self, ctx: ProcessContext):
        self.ipc = ctx.ipc
        self.state = ctx.shared_state
        self.config = ctx.config  # ConfigManager 实例
        self.running = True
        
        # 初始化各模块
        self.frame_reader = FrameReader(dataclasses.asdict(self.config.camera))
        self.strategy = DetectionStrategy(dataclasses.asdict(self.config.detector), self.state)
        self.analyzer = ResultAnalyzer(self.config.get_raw_dict())
        self.pipeline = None  # 稍后初始化
        
        # 统计
        self.detection_count = 0
        
        logger.info("AI 检测进程初始化完成（Pipeline架构）")
    
    def run(self):
        """主循环"""
        logger.info("🎥 AI 检测进程启动")
        
        try:
            # 1. 连接共享内存
            if not self.frame_reader.connect():
                logger.error("共享内存连接失败")
                return
            
            # 2. 初始化Pipeline
            self.pipeline = self._create_pipeline()
            if not self.pipeline.initialize():
                logger.error("Pipeline初始化失败")
                return
            
            # 3. 主循环
            last_heartbeat = time.time()
            last_stats_print = time.time()
            check_interval = 0.1
            
            while self.running:
                try:
                    # 读取新帧
                    frame_data = self.frame_reader.read_new_frame(copy=True)
                    
                    if frame_data is None:
                        # 无新帧，等待
                        time.sleep(check_interval)
                        
                        # 检查关闭信号
                        msg = self.ipc.receive(timeout=0.001)
                        if msg and msg.msg_type == MessageType.SHUTDOWN:
                            logger.info("收到关闭信号")
                            break
                        
                        continue
                    
                    frame, frame_id, timestamp = frame_data
                    
                    # 检测策略：是否跳过此帧
                    if not self.strategy.should_detect(frame_id):
                        continue
                    
                    # 执行Pipeline检测
                    result = self.pipeline.process(
                        frame,
                        metadata={
                            'frame_id': frame_id,
                            'timestamp': timestamp
                        }
                    )
                    
                    # 分析检测结果
                    analysis = self.analyzer.analyze(result.detections, result.metadata)
                    
                    # 发布检测结果（供OSD渲染）
                    if result.detections:
                        self._publish_detection_result(frame_id, timestamp, result.detections)
                    
                    # 报警处理
                    if analysis['should_alarm']:
                        self._report_alarm(analysis['alarm_data'])
                    
                    self.detection_count += 1
                    
                    # 定期发送心跳
                    if time.time() - last_heartbeat > 10:
                        self.ipc.send_heartbeat()
                        last_heartbeat = time.time()
                    
                    # 定期打印统计
                    if time.time() - last_stats_print > 60:
                        self._print_stats()
                        last_stats_print = time.time()
                    
                except Exception as e:
                    logger.error(f"检测循环异常: {e}", exc_info=True)
                    time.sleep(1)
        
        except KeyboardInterrupt:
            logger.info("检测到中断信号")
        finally:
            self._cleanup()
            logger.info("AI 检测进程退出")
    
    def _create_pipeline(self) -> DetectionPipeline:
        """创建检测Pipeline"""
        # 从配置文件读取Pipeline配置
        pipeline_config = self.config.get_raw('ai_detector.pipeline', [])
        
        # 如果配置为空，使用默认Pipeline
        if not pipeline_config:
            logger.warning("使用默认Pipeline配置")
            pipeline_config = self._get_default_pipeline_config()
        
        # 创建检测器列表
        detectors = create_detector_pipeline(pipeline_config)
        
        # 创建Pipeline
        pipeline = DetectionPipeline(detectors)
        
        return pipeline
    
    def _get_default_pipeline_config(self) -> list:
        """获取默认Pipeline配置"""
        detector = self.config.detector
        region_detector = detector.region_detector
        return [
            {
                'type': 'motion',
                'enabled': True,
                'config': {
                    'min_area': 500,
                    'threshold': 25,
                    'use_background_subtractor': True
                }
            },
            {
                'type': 'yolo',
                'enabled': True,
                'config': {
                    'model_path': detector.model_path,
                    'confidence_threshold': detector.confidence_threshold,
                    'target_classes': detector.target_classes,
                    'input_size': 320
                }
            },
            {
                'type': 'region',
                'enabled': region_detector is not None,
                'config': {
                    'regions': [r.to_dict() for r in region_detector.regions] if region_detector else [],
                    'overlap_threshold': region_detector.overlap_threshold if region_detector else 0.1
                }
            }
        ]
    
    def _publish_detection_result(self, frame_id: int, timestamp: float, detections: list):
        """发布检测结果（供OSD进程渲染）"""
        msg = create_message(
            msg_type='detection_result',
            target=ProcessName.STREAM_MANAGER,
            data={
                'frame_id': frame_id,
                'timestamp': timestamp,
                'detections': detections
            }
        )
        self.ipc.send_message(msg)
    
    def _report_alarm(self, alarm_data: dict):
        """上报异常事件"""
        logger.warning(
            f"🚨 报警！类型: {alarm_data['alarm_type']}, "
            f"目标数: {alarm_data['intrusion_count']}, "
            f"置信度: {alarm_data['confidence']:.2f}"
        )
        
        # 发送报警消息
        msg = create_message(
            msg_type=MessageType.ALARM_INTRUSION,
            target=ProcessName.SUPERVISOR,
            data=alarm_data
        )
        self.ipc.send_message(msg)
    
    def _print_stats(self):
        """打印统计信息"""
        logger.info("=" * 60)
        logger.info("AI 检测器统计信息")
        logger.info(f"检测总次数: {self.detection_count}")
        
        # Pipeline统计
        self.pipeline.print_stats()
        
        # 策略统计
        strategy_stats = self.strategy.get_stats()
        logger.info(f"当前状态: {strategy_stats['current_state']}")
        logger.info(f"当前检测间隔: {strategy_stats['current_interval']} 帧")
        
        # 分析器统计
        analyzer_stats = self.analyzer.get_stats()
        logger.info(f"报警总数: {analyzer_stats['alarm_count']}")
        if analyzer_stats['time_since_last_alarm'] >= 0:
            logger.info(f"距离上次报警: {analyzer_stats['time_since_last_alarm']:.1f} 秒")
        logger.info("=" * 60)
    
    def _cleanup(self):
        """清理资源"""
        try:
            # 打印最终统计
            self._print_stats()
            
            # 清理Pipeline
            if self.pipeline:
                self.pipeline.cleanup()
            
            # 关闭帧读取器
            self.frame_reader.close()
            
            logger.info("资源清理完成")
        except Exception as e:
            logger.error(f"清理资源失败: {e}")
