"""
OSD 消息分发器
负责接收IPC消息，转换为标准化数据格式，更新OSDDataStore
"""

from typing import Callable, Dict, Any
from utils.logger import setup_logger
from .data_store import OSDDataStore, OSDDataCategory

logger = setup_logger('osd_dispatcher')


class OSDMessageDispatcher:
    """
    OSD消息分发器
    
    职责：
    - 注册不同类型消息的处理器（Handler Pattern）
    - 将IPC消息数据转换为标准格式
    - 更新OSDDataStore
    - 提供扩展接口，便于添加新消息类型
    
    设计理念：
    - 开闭原则：添加新消息类型无需修改现有代码
    - 单一职责：只负责消息路由和数据适配
    - 易于测试：每个handler可独立测试
    """
    
    def __init__(self, data_store: OSDDataStore):
        """
        初始化消息分发器
        
        Args:
            data_store: OSD数据仓库实例
        """
        self.data_store = data_store
        self._handlers: Dict[str, Callable] = {}
        
        # 注册默认处理器
        self._register_default_handlers()
        
        logger.info("OSD消息分发器初始化完成")
    
    def _register_default_handlers(self):
        """注册默认的消息处理器"""
        self.register_handler('detection_result', self._handle_detection_result)
        self.register_handler('traffic_statistics', self._handle_traffic_statistics)
        self.register_handler('custom_annotations', self._handle_custom_annotations)
        self.register_handler('system_metadata', self._handle_system_metadata)
        
        logger.debug(f"已注册 {len(self._handlers)} 个默认消息处理器")
    
    def register_handler(self, msg_type: str, handler: Callable[[Dict[str, Any]], None]):
        """
        注册消息处理器
        
        Args:
            msg_type: 消息类型（如 'detection_result'）
            handler: 处理函数，接收消息数据字典，返回None
        
        Example:
            def my_handler(data):
                # 处理消息数据
                pass
            
            dispatcher.register_handler('my_message_type', my_handler)
        """
        if msg_type in self._handlers:
            logger.warning(f"消息类型 '{msg_type}' 已存在，将被覆盖")
        
        self._handlers[msg_type] = handler
        logger.info(f"✅ 注册消息处理器: {msg_type}")
    
    def unregister_handler(self, msg_type: str) -> bool:
        """
        注销消息处理器
        
        Args:
            msg_type: 消息类型
            
        Returns:
            bool: 注销成功返回True
        """
        if msg_type in self._handlers:
            del self._handlers[msg_type]
            logger.info(f"✅ 注销消息处理器: {msg_type}")
            return True
        else:
            logger.warning(f"消息类型 '{msg_type}' 不存在")
            return False
    
    def dispatch(self, msg: Dict[str, Any]):
        """
        分发消息到对应的处理器
        
        Args:
            msg: 消息字典，必须包含 'type' 和 'data' 字段
        
        Example:
            msg = {
                'type': 'detection_result',
                'data': {'detections': [...]}
            }
            dispatcher.dispatch(msg)
        """
        msg_type = msg.get('type')
        msg_data = msg.get('data', {})
        
        if not msg_type:
            logger.warning("消息缺少'type'字段，忽略")
            return
        
        handler = self._handlers.get(msg_type)
        
        if handler:
            try:
                handler(msg_data)
                logger.debug(f"✅ 消息处理成功: {msg_type}")
            except Exception as e:
                logger.error(f"❌ 消息处理失败 [{msg_type}]: {e}", exc_info=True)
        else:
            logger.debug(f"未找到处理器，忽略消息类型: {msg_type}")
    
    # ==================== 默认消息处理器 ====================
    
    def _handle_detection_result(self, data: Dict[str, Any]):
        """
        处理AI检测结果消息
        
        消息格式：
        {
            'frame_id': 123,
            'timestamp': 1234567890.123,
            'detections': [
                {
                    'class': 0,
                    'class_name': 'person',
                    'confidence': 0.95,
                    'bbox': [x, y, w, h],  # 归一化坐标
                    'keypoints': [[x1, y1, conf1], ...]  # 可选：骨架关键点
                },
                ...
            ]
        }
        """
        detections = data.get('detections', [])
        
        if detections:
            self.data_store.update_detections(detections)
            logger.debug(f"📦 更新检测结果：{len(detections)} 个目标")
        else:
            # 清空旧的检测结果
            self.data_store.clear_category(OSDDataCategory.DETECTIONS)
    
    def _handle_traffic_statistics(self, data: Dict[str, Any]):
        """
        处理客流统计消息（后期功能）
        
        消息格式：
        {
            'timestamp': 1234567890.123,
            'statistics': {
                'in_count': 10,
                'out_count': 8,
                'total_count': 18,
                'current_count': 2
            }
        }
        """
        statistics = data.get('statistics', {})
        
        if statistics:
            self.data_store.update_statistics(statistics)
            logger.debug(f"📊 更新统计数据：{statistics}")
    
    def _handle_custom_annotations(self, data: Dict[str, Any]):
        """
        处理自定义标注消息（如ROI区域、警戒线等）
        
        消息格式：
        {
            'annotations': [
                {
                    'type': 'roi',  # roi, line, zone等
                    'geometry': [[x1, y1], [x2, y2], ...],  # 归一化坐标
                    'label': 'ROI 1',
                    'color': [255, 0, 0]  # RGB
                },
                ...
            ]
        }
        """
        annotations = data.get('annotations', [])
        
        if annotations:
            self.data_store.update_annotations(annotations)
            logger.debug(f"🏷️ 更新标注：{len(annotations)} 个")
        else:
            self.data_store.clear_category(OSDDataCategory.ANNOTATIONS)
    
    def _handle_system_metadata(self, data: Dict[str, Any]):
        """
        处理系统元数据消息（状态、配置等）
        
        消息格式：
        {
            'state': 'alarm',  # safe, alert, alarm
            'mode': 'night',   # day, night
            'armed': True
        }
        """
        self.data_store.update_metadata(**data)
        logger.debug(f"⚙️ 更新元数据：{data}")
    
    # ==================== 工具方法 ====================
    
    def get_registered_types(self) -> list:
        """获取所有已注册的消息类型"""
        return list(self._handlers.keys())
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取分发器统计信息
        
        Returns:
            Dict: 统计信息
        """
        return {
            'registered_handlers': len(self._handlers),
            'handler_types': self.get_registered_types(),
            'data_store_stats': self.data_store.get_stats()
        }
