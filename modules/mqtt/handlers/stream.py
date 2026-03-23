"""
推流控制指令处理器
"""

from modules.mqtt.core.base import MQTTMessageHandler
from modules.mqtt.messages import CommandMessage
from core.ipc.message import CommandMessage as IPCCommandMessage, MessageType
from core.ipc.registry import ProcessName


class CommandStreamHandler(MQTTMessageHandler):
    """推流控制指令处理器"""
    
    def can_handle(self, topic: str, message: CommandMessage) -> bool:
        return "/command/stream" in topic
    
    def handle(self, topic: str, message: CommandMessage) -> bool:
        """
        处理推流控制指令
        
        支持的动作：
        - start: 开始推流
        - stop: 停止推流
        """
        action = message.get_action()
        self.logger.info(f"📥 收到推流控制指令: {action}, 消息内容: {message}")
        
        try:
            if action == 'start':
                stream_msg = IPCCommandMessage(
                    cmd_type=MessageType.CMD_START_STREAM,
                    target=ProcessName.STREAM_MANAGER,
                    cmd_data=message.data
                )
                self.ipc.send_message(stream_msg)
                self.send_response('stream', message.msg_id, 'success', '推流指令已接收')
                
            elif action == 'stop':
                stream_msg = IPCCommandMessage(
                    cmd_type=MessageType.CMD_STOP_STREAM,
                    target=ProcessName.STREAM_MANAGER,
                    cmd_data={}
                )
                self.ipc.send_message(stream_msg)
                self.send_response('stream', message.msg_id, 'success', '停止推流指令已接收')
                
            else:
                self.logger.warning(f"未知的推流指令: {action}")
                self.send_response('stream', message.msg_id, 'failed', 
                                 f'未知的指令: {action}', error_code=1000)
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"处理推流指令失败: {e}", exc_info=True)
            self.send_response('stream', message.msg_id, 'failed', 
                             str(e), error_code=5000)
            return False
