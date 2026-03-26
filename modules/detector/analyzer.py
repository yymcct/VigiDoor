"""
结果分析器
判断检测结果是否为异常事件，决定是否报警
"""

import time
from typing import Dict, Any, List
from urllib.parse import urlparse
from utils.logger import setup_logger

logger = setup_logger('result_analyzer')


class ResultAnalyzer:
    """
    结果分析器 - 异常判断和报警决策
    
    功能：
    1. 分析检测结果
    2. 判断是否为异常事件
    3. 生成报警数据
    4. 防抖逻辑（避免频繁报警）
    """
    
    def __init__(self, config: dict):
        """
        Args:
            config: 检测器配置
        """
        # 兼容传入 ai_detector 子配置或全量配置
        self.config = config
        self.ai_config = config.get('ai_detector', config)
        self.stream_config = config.get('stream', {})
        self.device_config = config.get('device', {})
        
        # 配置参数
        self.alarm_cooldown = self.ai_config.get('alarm_cooldown', 5.0)  # 报警冷却时间（秒）
        self.alert_cooldown = self.ai_config.get('alert_cooldown', 5.0)  # 警戒冷却时间（秒）
        self.min_confidence = self.ai_config.get('confidence_threshold', 0.5)
        
        # 状态
        self.last_alarm_time = 0
        self.last_alert_time = 0
        self.alarm_count = 0
        
        logger.info(f"结果分析器初始化: 报警冷却={self.alarm_cooldown}秒, 警戒冷却={self.alert_cooldown}秒")
    
    def analyze(self, detections: List[Dict[str, Any]], metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析检测结果
        
        Args:
            detections: 检测结果列表
            metadata: 元数据
        
        Returns:
            dict: 分析结果，包含:
                - is_anomaly: 是否为入侵异常
                - should_alarm: 是否应该报警（入侵+防抖通过）
                - should_alert: 是否应该触发警戒（有人但不在警戒区+防抖通过）
                - person_visible: 当前帧是否有人出现
                - alarm_data: 报警数据（如果需要报警）
        """
        person_visible = self._is_person_visible(detections)

        # 检查是否有检测结果
        if not detections:
            return {
                'is_anomaly': False,
                'should_alarm': False,
                'should_alert': False,
                'person_visible': False,
                'alarm_data': None
            }
        
        # 判断是否为入侵异常
        is_anomaly = self._is_anomaly(detections, metadata)
        
        if is_anomaly:
            # 入侵场景：检查防抖后决定是否报警
            should_alarm = self._should_alarm()
            if should_alarm:
                alarm_data = self._generate_alarm_data(detections, metadata)
                self.last_alarm_time = time.time()
                self.alarm_count += 1
            else:
                alarm_data = None
            return {
                'is_anomaly': True,
                'should_alarm': should_alarm,
                'should_alert': False,
                'person_visible': person_visible,
                'alarm_data': alarm_data
            }

        # 非入侵场景：有人但不在警戒区，检查是否触发警戒
        should_alert = self._should_alert_trigger(detections, metadata)
        if should_alert:
            self.last_alert_time = time.time()
        return {
            'is_anomaly': False,
            'should_alarm': False,
            'should_alert': should_alert,
            'person_visible': person_visible,
            'alarm_data': None
        }
    
    def _is_anomaly(self, detections: List[Dict[str, Any]], metadata: Dict[str, Any]) -> bool:
        """
        判断是否为异常事件
        
        策略：
        1. 检测到入侵区域的目标
        2. 或者检测到高置信度的目标
        """
        for detection in detections:
            # 检查是否有区域入侵标记
            if detection.get('is_intrusion', False):
                return True
            
            # 检查置信度
            if detection.get('confidence', 0) >= self.min_confidence:
                # 检测到高置信度目标也认为是异常
                # （如果没有配置区域检测器）
                if not metadata.get('has_region_detector', False):
                    return True
        
        return False
    
    def _is_person_visible(self, detections: List[Dict[str, Any]]) -> bool:
        """判断当前帧是否有人出现（置信度达到阈值）"""
        return any(d.get('confidence', 0) >= self.min_confidence for d in detections)

    def _should_alert_trigger(self, detections: List[Dict[str, Any]], metadata: Dict[str, Any]) -> bool:
        """
        判断是否应触发警戒状态（有人但不在警戒区，防抖通过）。
        仅当配置了区域检测器时才有效。
        """
        if not metadata.get('has_region_detector', False):
            return False
        if not self._is_person_visible(detections):
            return False
        current_time = time.time()
        if current_time - self.last_alert_time < self.alert_cooldown:
            logger.debug(f"警戒冷却中（剩余 {self.alert_cooldown - (current_time - self.last_alert_time):.1f}秒）")
            return False
        return True

    def _should_alarm(self) -> bool:
        """
        判断是否应该报警（防抖逻辑）
        
        Returns:
            bool: 是否应该报警
        """
        current_time = time.time()
        
        # 检查是否在冷却时间内
        if current_time - self.last_alarm_time < self.alarm_cooldown:
            logger.debug(f"报警冷却中（剩余 {self.alarm_cooldown - (current_time - self.last_alarm_time):.1f}秒）")
            return False
        
        return True
    
    def _generate_alarm_data(self, detections: List[Dict[str, Any]], metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成报警数据
        
        Returns:
            dict: 报警数据
        """
        # 找到置信度最高的检测
        max_confidence_detection = max(detections, key=lambda d: d.get('confidence', 0))
        
        # 获取入侵目标
        intrusion_detections = [d for d in detections if d.get('is_intrusion', False)]
        
        # 确定告警类型和严重程度
        if intrusion_detections:
            severity = 'high'  # 入侵事件为高级别
        else:
            severity = 'medium'
        
        # 生成快照路径
        timestamp = metadata.get('timestamp', time.time())
        snapshot_path = f"data/snapshots/alarm_{int(timestamp)}.jpg"
        
        alarm_data = {
            'alarm_type': "alarm_intrusion",
            "source": "camera_1",
            'confidence': max_confidence_detection.get('confidence', 0),
            'intrusion_count': len(intrusion_detections),
            "severity": severity, 
            'snapshot_urls': [snapshot_path],  # 快照URL列表（本地路径，后续可转换为URL）
            'video_urls': self._build_video_urls(metadata),  # 视频URL列表
            'timestamp': timestamp  # 保留时间戳用于IPC消息
        }
        
        return alarm_data

    #TODO 优化视频URL构建逻辑
    def _build_video_urls(self, metadata: Dict[str, Any]) -> List[str]:
        """根据 zlm_server 和 device_id 构建 WebRTC 回放URL"""
        zlm_server = metadata.get('zlm_server') or self.stream_config.get('zlm_server')
        device_id = metadata.get('device_id') or self.device_config.get('id')

        if not zlm_server or not device_id:
            return []

        parsed = urlparse(zlm_server)
        host = parsed.hostname
        app = parsed.path.lstrip('/') or 'live'

        if not host:
            return []

        url = f"https://{host}:8443/webrtc/?app={app}&stream={device_id}"
        return [url]
    
    def reset_cooldown(self):
        """重置冷却时间（立即允许报警）"""
        self.last_alarm_time = 0
        logger.debug("报警冷却已重置")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        current_time = time.time()
        time_since_last_alarm = current_time - self.last_alarm_time if self.last_alarm_time > 0 else -1
        time_since_last_alert = current_time - self.last_alert_time if self.last_alert_time > 0 else -1
        
        return {
            'alarm_count': self.alarm_count,
            'last_alarm_time': self.last_alarm_time,
            'time_since_last_alarm': time_since_last_alarm,
            'is_in_cooldown': time_since_last_alarm >= 0 and time_since_last_alarm < self.alarm_cooldown,
            'last_alert_time': self.last_alert_time,
            'time_since_last_alert': time_since_last_alert,
            'is_in_alert_cooldown': time_since_last_alert >= 0 and time_since_last_alert < self.alert_cooldown,
        }
