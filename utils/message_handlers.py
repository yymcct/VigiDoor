"""
消息处理器框架
使用策略模式处理不同类型的消息，支持灵活扩展
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging


class MessageHandler(ABC):
    """消息处理器基类"""
    
    def __init__(self, supervisor):
        """
        初始化消息处理器
        
        Args:
            supervisor: Supervisor 实例的引用
        """
        self.supervisor = supervisor
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def handle(self, msg: Dict[str, Any]) -> None:
        """
        处理消息
        
        Args:
            msg: 消息字典
        """
        pass
    
    @abstractmethod
    def get_message_type(self) -> str:
        """
        获取该处理器处理的消息类型
        
        Returns:
            消息类型字符串
        """
        pass


class HeartbeatHandler(MessageHandler):
    """心跳消息处理器"""
    
    def get_message_type(self) -> str:
        return 'heartbeat'
    
    def handle(self, msg: Dict[str, Any]) -> None:
        """处理心跳消息"""
        process_name = msg.get('from')
        if process_name:
            import time
            self.supervisor.shared_state['last_heartbeat'][process_name] = time.time()
            self.logger.debug(f"收到 {process_name} 心跳")


class AnomalyDetectedHandler(MessageHandler):
    """异常检测消息处理器"""
    
    def get_message_type(self) -> str:
        return 'anomaly_detected'
    
    def handle(self, msg: Dict[str, Any]) -> None:
        """处理 AI 检测到的异常"""
        data = msg.get('data', {})
        self.logger.warning(f"🚨 检测到异常: {data}")
        
        # 切换到报警状态
        self._set_global_state('alarm')
        
        # 通知 MQTT 上报
        self.supervisor.ipc_queue.put({
            'type': 'report_alarm',
            'to': 'mqtt_client',
            'data': data
        })
        
        # 通知硬件控制切换灯光
        self.supervisor.ipc_queue.put({
            'type': 'set_light',
            'to': 'device_controller',
            'mode': 'alarm'
        })
    
    def _set_global_state(self, state: str):
        """设置全局状态"""
        old_state = self.supervisor.shared_state['global_state']
        if old_state != state:
            self.supervisor.shared_state['global_state'] = state
            self.logger.info(f"🔄 全局状态切换: {old_state} → {state}")


class AudioAnomalyHandler(MessageHandler):
    """音频异常消息处理器"""
    
    def get_message_type(self) -> str:
        return 'audio_anomaly'
    
    def handle(self, msg: Dict[str, Any]) -> None:
        """处理音频异常"""
        data = msg.get('data', {})
        self.logger.warning(f"🔊 检测到异常声音")
        
        # 切换到警戒状态
        self._set_global_state('alert')
        
        # 通知硬件控制
        self.supervisor.ipc_queue.put({
            'type': 'set_light',
            'to': 'device_controller',
            'mode': 'alert'
        })
    
    def _set_global_state(self, state: str):
        """设置全局状态"""
        old_state = self.supervisor.shared_state['global_state']
        if old_state != state:
            self.supervisor.shared_state['global_state'] = state
            self.logger.info(f"🔄 全局状态切换: {old_state} → {state}")


class MqttCommandHandler(MessageHandler):
    """MQTT 平台指令处理器"""
    
    def get_message_type(self) -> str:
        return 'mqtt_command'
    
    def handle(self, msg: Dict[str, Any]) -> None:
        """处理平台下发的指令"""
        action = msg.get('action')
        self.logger.info(f"📥 收到平台指令: {action}")
        
        # 根据不同的 action 分发到对应的处理方法
        handler_map = {
            'start_stream': self._handle_start_stream,
            'stop_stream': self._handle_stop_stream,
            'remote_speak': self._handle_remote_speak,
        }
        
        handler = handler_map.get(action)
        if handler:
            handler(msg)
        else:
            self.logger.warning(f"未知的平台指令: {action}")
    
    def _handle_start_stream(self, msg: Dict[str, Any]) -> None:
        """处理开始推流指令"""
        self.supervisor.ipc_queue.put({
            'type': 'start_stream',
            'to': 'stream_manager',
            'data': msg.get('data')
        })
    
    def _handle_stop_stream(self, msg: Dict[str, Any]) -> None:
        """处理停止推流指令"""
        self.supervisor.ipc_queue.put({
            'type': 'stop_stream',
            'to': 'stream_manager'
        })
    
    def _handle_remote_speak(self, msg: Dict[str, Any]) -> None:
        """处理远程喊话指令"""
        self.supervisor.ipc_queue.put({
            'type': 'play_audio',
            'to': 'audio_processor',
            'data': msg.get('data')
        })


class MessageRouter:
    """
    消息路由器
    负责管理和分发消息到对应的处理器
    """
    
    def __init__(self, supervisor):
        """
        初始化消息路由器
        
        Args:
            supervisor: Supervisor 实例的引用
        """
        self.supervisor = supervisor
        self.logger = logging.getLogger('MessageRouter')
        self.handlers: Dict[str, MessageHandler] = {}
        
        # 注册默认处理器
        self._register_default_handlers()
    
    def _register_default_handlers(self):
        """注册默认的消息处理器"""
        default_handlers = [
            HeartbeatHandler(self.supervisor),
            AnomalyDetectedHandler(self.supervisor),
            AudioAnomalyHandler(self.supervisor),
            MqttCommandHandler(self.supervisor),
        ]
        
        for handler in default_handlers:
            self.register_handler(handler)
        
        self.logger.info(f"已注册 {len(self.handlers)} 个消息处理器")
    
    def register_handler(self, handler: MessageHandler) -> None:
        """
        注册消息处理器
        
        Args:
            handler: 消息处理器实例
        """
        msg_type = handler.get_message_type()
        if msg_type in self.handlers:
            self.logger.warning(f"消息类型 {msg_type} 的处理器已存在，将被覆盖")
        
        self.handlers[msg_type] = handler
        self.logger.debug(f"注册处理器: {msg_type} -> {handler.__class__.__name__}")
    
    def unregister_handler(self, msg_type: str) -> None:
        """
        注销消息处理器
        
        Args:
            msg_type: 消息类型
        """
        if msg_type in self.handlers:
            del self.handlers[msg_type]
            self.logger.debug(f"注销处理器: {msg_type}")
    
    def route(self, msg: Dict[str, Any]) -> bool:
        """
        路由消息到对应的处理器
        
        Args:
            msg: 消息字典
            
        Returns:
            是否成功处理
        """
        msg_type = msg.get('type')
        
        if not msg_type:
            self.logger.warning("收到无类型的消息")
            return False
        
        handler = self.handlers.get(msg_type)
        
        if handler:
            try:
                handler.handle(msg)
                return True
            except Exception as e:
                self.logger.error(f"处理消息 {msg_type} 时出错: {e}", exc_info=True)
                return False
        else:
            self.logger.debug(f"未找到消息类型 {msg_type} 的处理器")
            return False
    
    def get_registered_types(self) -> list:
        """
        获取所有已注册的消息类型
        
        Returns:
            消息类型列表
        """
        return list(self.handlers.keys())
