"""
MQTT 话题管理器
统一管理所有 MQTT 话题模板，避免硬编码和拼写错误
"""
from string import Formatter


class TopicManager:
    """
    MQTT 话题管理器
    
    功能：
    1. 集中管理所有话题模板
    2. 提供话题构建方法
    3. 支持通配符订阅模式
    4. 话题解析和路由
    """
    
    # 命名空间
    NAMESPACE = "vigidoor"
    
    # ==================== 上行话题（设备→平台）====================
    # 2.1 设备生命周期管理
    LIFECYCLE_ONLINE = "{ns}/up/{device_id}/lifecycle/online"
    LIFECYCLE_OFFLINE = "{ns}/up/{device_id}/lifecycle/offline"
    LIFECYCLE_HEARTBEAT = "{ns}/up/{device_id}/lifecycle/heartbeat"
    
    # 2.2 告警事件上报
    ALARM_INTRUSION = "{ns}/up/{device_id}/alarm/intrusion"
    ALARM_SYSTEM = "{ns}/up/{device_id}/alarm/system"
    

    
    # 2.3 系统健康状态上报
    HEALTH_METRICS = "$oc/devices/{device_id}/sys/properties/report"
    
    
    HEALTH_PROCESS = "{ns}/up/{device_id}/health/process"
    
    # 2.4 业务状态上报
    STATUS_STREAM = "{ns}/up/{device_id}/status/stream"
    STATUS_HARDWARE = "{ns}/up/{device_id}/status/hardware"
    
    # 2.5 日志上报（可选）
    LOG_ERROR = "{ns}/up/{device_id}/log/error"
    
    # 2.6 配置响应
    CONFIG_RESPONSE = "{ns}/up/{device_id}/config/response"
    
    # 2.7 指令响应
    RESPONSE_STREAM = "{ns}/up/{device_id}/response/stream"
    RESPONSE_AUDIO = "{ns}/up/{device_id}/response/audio"
    RESPONSE_DEVICE = "{ns}/up/{device_id}/response/device"
    RESPONSE_SECURITY = "{ns}/up/{device_id}/response/security"  # 布防/撤防响应
    
    # ==================== 下行话题（平台→设备）====================
    
    # 3.1 远程控制指令
    COMMAND_STREAM = "{ns}/down/{device_id}/command/stream"
    COMMAND_AUDIO = "{ns}/down/{device_id}/command/audio"
    COMMAND_DEVICE = "{ns}/down/{device_id}/command/device"
    COMMAND_SECURITY = "{ns}/down/{device_id}/command/security"  # 布防/撤防
    
    # 3.2 配置管理
    CONFIG_UPDATE = "{ns}/down/{device_id}/config/update"
    CONFIG_QUERY = "{ns}/down/{device_id}/config/query"
    
    # 3.3 固件升级（未来扩展）
    OTA_UPGRADE = "{ns}/down/{device_id}/ota/upgrade"
    
    # ==================== 订阅模式（通配符）====================
    
    # 下行指令通配符（设备端订阅）
    SUBSCRIBE_ALL_COMMANDS = "{ns}/down/{device_id}/command/#"
    SUBSCRIBE_ALL_CONFIG = "{ns}/down/{device_id}/config/#"
    SUBSCRIBE_ALL_OTA = "{ns}/down/{device_id}/ota/#"
    
    # 上行消息通配符（平台端订阅）
    SUBSCRIBE_ALL_DEVICES_LIFECYCLE = "{ns}/up/+/lifecycle/#"
    SUBSCRIBE_ALL_DEVICES_ALARM = "{ns}/up/+/alarm/#"
    SUBSCRIBE_ALL_DEVICES_HEALTH = "{ns}/up/+/health/#"
    SUBSCRIBE_ALL_DEVICES_STATUS = "{ns}/up/+/status/#"
    SUBSCRIBE_DEVICE_ALL = "{ns}/up/{device_id}/#"
    
    def __init__(self, device_id: str, namespace: str = None):
        """
        初始化话题管理器
        
        Args:
            device_id: 设备唯一标识
            namespace: 命名空间（可选，默认使用 NAMESPACE）
        """
        self.device_id = device_id
        self.namespace = namespace or self.NAMESPACE
    
    def build(self, template: str, **kwargs) -> str:
        """
        构建具体话题
        
        Args:
            template: 话题模板（如 TopicManager.ALARM_INTRUSION 或 TopicManager.HEALTH_METRICS）
            **kwargs: 额外参数（默认会注入 ns 和 device_id）
        
        Returns:
            完整的话题字符串
        
        Examples:
            >>> tm = TopicManager("RPI_001")
            >>> tm.build(TopicManager.ALARM_INTRUSION)
            'vigidoor/up/RPI_001/alarm/intrusion'
            >>> tm.build(TopicManager.HEALTH_METRICS)
            '$oc/devices/RPI_001/sys/properties/report'
        """
        # 准备默认参数
        params = {
            'ns': self.namespace,
            'device_id': self.device_id,
            **kwargs
        }
        
        # 提取模板中实际需要的字段名
        formatter = Formatter()
        field_names = {field_name for _, field_name, _, _ in formatter.parse(template) if field_name}
        
        # 只传递模板中需要的参数，避免传递多余参数
        filtered_params = {k: v for k, v in params.items() if k in field_names}
        
        return template.format(**filtered_params)
    
    def get_device_subscribe_topics(self, qos_map: dict = None) -> list:
        """
        获取设备端需要订阅的话题列表
        
        Args:
            qos_map: QoS 映射表（可选）
                     {
                         'command': 1,
                         'config': 2,
                         'ota': 2
                     }
        
        Returns:
            [(topic, qos), ...] 格式的订阅列表
        
        Examples:
            >>> tm = TopicManager("RPI_001")
            >>> tm.get_device_subscribe_topics()
            [
                ('vigidoor/down/RPI_001/command/#', 1),
                ('vigidoor/down/RPI_001/config/#', 2),
                ('vigidoor/down/RPI_001/ota/#', 2)
            ]
        """
        if qos_map is None:
            qos_map = {
                'command': 1,
                'config': 2,
                'ota': 2
            }
        
        return [
            (self.build(self.SUBSCRIBE_ALL_COMMANDS), qos_map.get('command', 1)),
            (self.build(self.SUBSCRIBE_ALL_CONFIG), qos_map.get('config', 2)),
            (self.build(self.SUBSCRIBE_ALL_OTA), qos_map.get('ota', 2)),
        ]
    
    def parse_topic(self, topic: str) -> dict:
        """
        解析话题，提取关键信息
        
        Args:
            topic: 完整的话题字符串
        
        Returns:
            解析结果字典
            {
                'namespace': str,
                'direction': 'up' | 'down',
                'device_id': str,
                'category': str,
                'sub_category': str | None
            }
        
        Examples:
            >>> tm = TopicManager("RPI_001")
            >>> tm.parse_topic("vigidoor/down/RPI_001/command/stream")
            {
                'namespace': 'vigidoor',
                'direction': 'down',
                'device_id': 'RPI_001',
                'category': 'command',
                'sub_category': 'stream'
            }
        """
        parts = topic.split('/')
        
        if len(parts) < 4:
            return None
        
        result = {
            'namespace': parts[0],
            'direction': parts[1],
            'device_id': parts[2],
            'category': parts[3] if len(parts) > 3 else None,
            'sub_category': parts[4] if len(parts) > 4 else None
        }
        
        return result
    
    def matches_pattern(self, topic: str, pattern: str) -> bool:
        """
        判断话题是否匹配指定模式（支持 MQTT 通配符）
        
        Args:
            topic: 实际话题
            pattern: 模式（支持 + 和 # 通配符）
        
        Returns:
            是否匹配
        
        Examples:
            >>> tm = TopicManager("RPI_001")
            >>> tm.matches_pattern(
            ...     "vigidoor/down/RPI_001/command/stream",
            ...     "vigidoor/down/+/command/#"
            ... )
            True
        """
        topic_parts = topic.split('/')
        pattern_parts = pattern.split('/')
        
        # # 通配符匹配所有后续层级
        if '#' in pattern_parts:
            hash_index = pattern_parts.index('#')
            pattern_parts = pattern_parts[:hash_index + 1]
            
            if len(topic_parts) < len(pattern_parts) - 1:
                return False
            
            for i, part in enumerate(pattern_parts[:-1]):
                if part != '+' and part != topic_parts[i]:
                    return False
            return True
        
        # 长度必须匹配
        if len(topic_parts) != len(pattern_parts):
            return False
        
        # 逐层匹配（+ 匹配单层）
        for topic_part, pattern_part in zip(topic_parts, pattern_parts):
            if pattern_part != '+' and pattern_part != topic_part:
                return False
        
        return True
    
    @classmethod
    def get_qos_for_topic(cls, topic_template: str) -> int:
        """
        根据话题模板获取推荐的 QoS 级别
        
        Args:
            topic_template: 话题模板
        
        Returns:
            QoS 级别 (0, 1, 2)
        """
        # QoS 0: 心跳、状态查询
        qos_0_topics = [
            cls.LIFECYCLE_HEARTBEAT,
            cls.LOG_ERROR,
        ]
        
        # QoS 2: 关键配置、固件更新
        qos_2_topics = [
            cls.CONFIG_UPDATE,
            cls.OTA_UPGRADE,
        ]
        
        if topic_template in qos_0_topics:
            return 0
        elif topic_template in qos_2_topics:
            return 2
        else:
            # 默认 QoS 1: 告警、指令、健康上报
            return 1
    
    @classmethod
    def should_retain(cls, topic_template: str) -> bool:
        """
        判断消息是否应该设置 retain 标志
        
        Args:
            topic_template: 话题模板
        
        Returns:
            是否保留消息
        """
        # 需要保留的话题（便于查询最后状态）
        retain_topics = [
            cls.LIFECYCLE_ONLINE,
            cls.LIFECYCLE_OFFLINE,
        ]
        
        return topic_template in retain_topics
