"""
音频控制指令处理器（远程喊话）
"""

from modules.mqtt.core.base import MQTTMessageHandler
from modules.mqtt.messages import CommandMessage


class CommandAudioHandler(MQTTMessageHandler):
    """音频控制指令处理器（远程喊话）"""
    
    def can_handle(self, topic: str, message: CommandMessage) -> bool:
        return "/command/audio" in topic
    
    def handle(self, topic: str, message: CommandMessage) -> bool:
        """
        处理音频控制指令
        
        支持的动作：
        - speak: 远程喊话
        """
        action = message.get_action()
        self.logger.info(f"📥 收到音频控制指令: {action}")
        
        try:
            if action == 'speak':
                # 转发给 audio_processor 进程
                self.ipc.send(
                    msg_type='play_audio',
                    target='audio_processor',
                    data=message.data
                )
                self.send_response('audio', message.msg_id, 'success', '喊话指令已接收')
                
            else:
                self.logger.warning(f"未知的音频指令: {action}")
                self.send_response('audio', message.msg_id, 'failed', 
                                 f'未知的指令: {action}', error_code=1000)
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"处理音频指令失败: {e}", exc_info=True)
            self.send_response('audio', message.msg_id, 'failed', 
                             str(e), error_code=5000)
            return False
