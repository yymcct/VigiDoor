"""
MQTT 消息发布器
统一管理所有 MQTT 消息的发布逻辑，消除重复代码
"""

from collections import deque
from typing import Optional
import time
import logging
import json

from modules.mqtt.topics import TopicManager
from modules.mqtt.messages import MQTTMessageBase


class MQTTPublisher:
    """
    MQTT 消息发布器
    
    功能：
    1. 统一的消息发布接口
    2. 自动序列化消息对象
    3. 消息缓存和重发机制
    4. 自动设置 QoS 和 Retain 标志
    5. 发布失败处理和重试
    """
    
    def __init__(self, mqtt_client, topic_manager: TopicManager, 
                 logger: Optional[logging.Logger] = None,
                 max_buffer_size: int = 200):
        """
        初始化发布器
        
        Args:
            mqtt_client: paho.mqtt.client.Client 实例
            topic_manager: 话题管理器实例
            logger: 日志记录器（可选）
            max_buffer_size: 消息缓冲区最大大小
        """
        self.client = mqtt_client
        self.tm = topic_manager
        self.logger = logger or logging.getLogger('mqtt_publisher')
        
        # 消息缓冲队列（离线时缓存消息）
        self.message_buffer = deque(maxlen=max_buffer_size)
        
        # 统计信息
        self.stats = {
            'published': 0,
            'failed': 0,
            'buffered': 0,
            'dropped': 0
        }
    
    def _publish_raw(self, topic: str, payload: str, qos: int, retain: bool, 
                     msg_id: Optional[str] = None) -> bool:
        """
        底层发布方法（内部使用）
        
        Args:
            topic: 完整话题
            payload: JSON字符串负载
            qos: QoS 级别
            retain: 保留标志
            msg_id: 消息ID（用于日志）
        
        Returns:
            是否成功发布
        """
        try:
            result = self.client.publish(topic, payload, qos=qos, retain=retain)
            
            # 检查发布结果
            if result.rc == 0:  # mqtt.MQTT_ERR_SUCCESS
                self.stats['published'] += 1
                log_msg = f"📤 已发布: {topic} (QoS={qos}, Retain={retain}"
                if msg_id:
                    log_msg += f", msg_id={msg_id}"
                log_msg += ")"
                self.logger.debug(log_msg)
                return True
            else:
                raise Exception(f"发布失败，返回码: {result.rc}")
                
        except Exception as e:
            self.logger.error(f"发布消息失败: {e}")
            self.stats['failed'] += 1
            
            # 缓存消息待重发
            self._buffer_message(topic, payload, qos, retain)
            return False
    
    def publish(self, 
                topic_template: str, 
                message: MQTTMessageBase,
                qos: Optional[int] = None,
                retain: Optional[bool] = None) -> bool:
        """
        发布消息（统一入口，使用消息对象）
        
        Args:
            topic_template: 话题模板（如 TopicManager.ALARM_INTRUSION）
            message: 消息对象
            qos: QoS 级别（可选，默认根据话题自动判断）
            retain: 是否保留消息（可选，默认根据话题自动判断）
        
        Returns:
            是否成功发布
        
        Examples:
            >>> publisher = MQTTPublisher(client, topic_manager)
            >>> msg = AlarmIntrusionMessage(
            ...     device_id="RPI_001",
            ...     data={"alarm_type": "person_detected", "confidence": 0.95}
            ... )
            >>> publisher.publish(TopicManager.ALARM_INTRUSION, msg)
            True
        """
        # 构建话题
        topic = self.tm.build(topic_template)
        
        # 序列化消息
        payload = message.to_json()
        
        # 自动确定 QoS 和 Retain
        if qos is None:
            qos = TopicManager.get_qos_for_topic(topic_template)
        if retain is None:
            retain = TopicManager.should_retain(topic_template)
        
        # 调用底层发布方法
        return self._publish_raw(topic, payload, qos, retain, msg_id=message.msg_id)
    
    def publish_json(self, 
                     topic_template: str, 
                     payload: str,
                     qos: Optional[int] = None,
                     retain: Optional[bool] = None) -> bool:
        """
        发布消息（直接传入JSON字符串）
        
        Args:
            topic_template: 话题模板（如 TopicManager.ALARM_INTRUSION）
            payload: JSON字符串负载
            qos: QoS 级别（可选，默认根据话题自动判断）
            retain: 是否保留消息（可选，默认根据话题自动判断）
        
        Returns:
            是否成功发布
        
        Examples:
            >>> publisher = MQTTPublisher(client, topic_manager)
            >>> payload = '{"device_id": "RPI_001", "alarm_type": "intrusion"}'
            >>> publisher.publish_json(TopicManager.ALARM_INTRUSION, payload)
            True
        """
        # 构建话题
        topic = self.tm.build(topic_template)
        
        # 自动确定 QoS 和 Retain
        if qos is None:
            qos = TopicManager.get_qos_for_topic(topic_template)
        if retain is None:
            retain = TopicManager.should_retain(topic_template)
        
        # 调用底层发布方法
        return self._publish_raw(topic, payload, qos, retain)
    
    def _buffer_message(self, topic: str, payload: str, qos: int, retain: bool):
        """
        缓存消息到缓冲区
        
        Args:
            topic: 话题
            payload: 消息负载
            qos: QoS 级别
            retain: 保留标志
        """
        buffer_item = {
            'topic': topic,
            'payload': payload,
            'qos': qos,
            'retain': retain,
            'timestamp': time.time()
        }
        
        # 检查缓冲区是否已满
        if len(self.message_buffer) >= self.message_buffer.maxlen:
            self.stats['dropped'] += 1
            self.logger.warning("⚠️ 消息缓冲区已满，将丢弃最旧的消息")
        
        self.message_buffer.append(buffer_item)
        self.stats['buffered'] += 1
        self.logger.warning(
            f"⚠️ MQTT 未连接，消息已缓存（队列: {len(self.message_buffer)}/{self.message_buffer.maxlen}）"
        )
    
    def flush_buffer(self) -> int:
        """
        发送缓冲区中的所有消息
        
        Returns:
            成功发送的消息数量
        """
        if not self.message_buffer:
            return 0
        
        self.logger.info(f"📤 开始发送缓存的 {len(self.message_buffer)} 条消息")
        
        success_count = 0
        failed_items = []
        
        while self.message_buffer:
            item = self.message_buffer.popleft()
            
            try:
                result = self.client.publish(
                    item['topic'], 
                    item['payload'], 
                    qos=item['qos'],
                    retain=item['retain']
                )
                
                if result.rc == 0:
                    success_count += 1
                else:
                    failed_items.append(item)
                    
            except Exception as e:
                self.logger.error(f"重发消息失败: {e}")
                failed_items.append(item)
        
        # 将失败的消息放回缓冲区
        for item in failed_items:
            self.message_buffer.append(item)
        
        self.logger.info(
            f"✅ 成功发送 {success_count} 条消息，"
            f"失败 {len(failed_items)} 条"
        )
        
        return success_count
    
    def clear_expired_buffer(self, max_age_seconds: int = 3600):
        """
        清理过期的缓存消息
        
        Args:
            max_age_seconds: 消息最大存活时间（秒），默认1小时
        """
        now = time.time()
        original_size = len(self.message_buffer)
        
        # 过滤掉过期消息
        self.message_buffer = deque(
            (item for item in self.message_buffer 
             if now - item['timestamp'] < max_age_seconds),
            maxlen=self.message_buffer.maxlen
        )
        
        removed_count = original_size - len(self.message_buffer)
        if removed_count > 0:
            self.logger.info(f"🗑️  清理了 {removed_count} 条过期消息")
    
    def get_stats(self) -> dict:
        """获取发布统计信息"""
        return {
            **self.stats,
            'buffer_size': len(self.message_buffer),
            'buffer_capacity': self.message_buffer.maxlen
        }
    
    # ==================== 快捷发布方法 ====================
    
    def publish_lifecycle_online(self, device_name: str, location: str, 
                                 firmware_version: str, ip_address: str,
                                 mac_address: str) -> bool:
        """发布设备上线消息"""
        from modules.mqtt.messages import LifecycleOnlineMessage
        
        msg = LifecycleOnlineMessage(
            device_id=self.tm.device_id,
            data={
                "device_name": device_name,
                "location": location,
                "firmware_version": firmware_version,
                "ip_address": ip_address,
                "mac_address": mac_address
            }
        )
        return self.publish(TopicManager.LIFECYCLE_ONLINE, msg)
    
    def publish_lifecycle_heartbeat(self, uptime: int, global_state: str) -> bool:
        """发布设备心跳"""
        from modules.mqtt.messages import LifecycleHeartbeatMessage
        
        msg = LifecycleHeartbeatMessage(
            device_id=self.tm.device_id,
            data={
                "uptime": uptime,
                "global_state": global_state
            }
        )
        return self.publish(TopicManager.LIFECYCLE_HEARTBEAT, msg)
    
    def publish_alarm_intrusion(self, alarm_data: dict) -> bool:
        """发布入侵告警（统一告警类型）"""
        from modules.mqtt.messages.alarm import AlarmIntrusionMessage

        msg = AlarmIntrusionMessage(
            device_id=self.tm.device_id,
            data=alarm_data
        )
        return self.publish(TopicManager.ALARM_INTRUSION, msg)


    def publish_alarm_system(self, alarm_data: dict) -> bool:
        """发布系统级严重告警（强制 QoS=2）"""
        from modules.mqtt.messages import AlarmSystemMessage
        
        msg = AlarmSystemMessage(
            device_id=self.tm.device_id,
            data=alarm_data
        )
        return self.publish(TopicManager.ALARM_SYSTEM, msg, qos=2)
    
    def publish_health_metrics(self, metrics: dict) -> bool:
        """
        发布系统健康指标
        
        Args:
            metrics: 健康指标属性字典，应包含以下字段：
                - cpu_usage: CPU使用率
                - memory_usage: 内存使用率
                - disk_usage: 磁盘使用率
                - temperature: 温度
                - uptime: 运行时间
                - network: 网络信息
                - process_status: 进程状态
        """
        
        msg = {
            "services": [
                {
                    "service_id": "metrics",
                    "properties": metrics
                }
            ]
        }
        self.logger.debug(f"📊 发布健康指标: {json.dumps(msg, ensure_ascii=False)}")
        return self.publish_json(TopicManager.HEALTH_METRICS, json.dumps(msg))
    
    def publish_health_process(self, process_data: dict) -> bool:
        """发布进程状态变更"""
        from modules.mqtt.messages import HealthProcessMessage
        
        msg = HealthProcessMessage(
            device_id=self.tm.device_id,
            data=process_data
        )
        return self.publish(TopicManager.HEALTH_PROCESS, msg)
    
    def publish_status_stream(self, stream_data: dict) -> bool:
        """发布推流状态变更"""
        from modules.mqtt.messages import StatusStreamMessage
        
        msg = StatusStreamMessage(
            device_id=self.tm.device_id,
            data=stream_data
        )
        return self.publish(TopicManager.STATUS_STREAM, msg)
    
    def publish_status_hardware(self, hardware_data: dict) -> bool:
        """发布硬件状态变更"""
        from modules.mqtt.messages import StatusHardwareMessage
        
        msg = StatusHardwareMessage(
            device_id=self.tm.device_id,
            data=hardware_data
        )
        return self.publish(TopicManager.STATUS_HARDWARE, msg)
    
    def publish_response(self, command_type: str, request_msg_id: str,
                        status: str, message: str = "", 
                        error_code: Optional[int] = None) -> bool:
        """
        发布指令响应
        
        Args:
            command_type: 指令类型（stream/audio/device）
            request_msg_id: 原始请求的消息ID
            status: 响应状态（success/failed/timeout）
            message: 响应消息
            error_code: 错误码（可选）
        """
        from modules.mqtt.messages import ResponseMessage
        
        # 根据类型选择响应话题
        topic_map = {
            'stream':   TopicManager.RESPONSE_STREAM,
            'audio':    TopicManager.RESPONSE_AUDIO,
            'device':   TopicManager.RESPONSE_DEVICE,
            'security': TopicManager.RESPONSE_SECURITY,
        }
        
        topic_template = topic_map.get(command_type, TopicManager.RESPONSE_DEVICE)
        
        msg = ResponseMessage(
            device_id=self.tm.device_id,
            data={
                "request_msg_id": request_msg_id,
                "status": status,
                "message": message,
                "error_code": error_code
            }
        )
        return self.publish(topic_template, msg)
