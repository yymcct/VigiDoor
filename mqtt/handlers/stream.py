"""
推流控制指令处理器
"""

from mqtt.core.base import MQTTMessageHandler
from mqtt.messages import CommandMessage


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
        self.logger.info(f"📥 收到推流控制指令: {action}")
        
        try:
            if action == 'start':
                # 转发给 stream_manager 进程
                self.ipc.send(
                    msg_type='start_stream',
                    target='stream_manager',
                    data=message.data
                )
                self.send_response('stream', message.msg_id, 'success', '推流指令已接收')
                
            elif action == 'stop':
                # 转发给 stream_manager 进程
                self.ipc.send(
                    msg_type='stop_stream',
                    target='stream_manager'
                )
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
