"""
音频控制指令处理器（远程喊话）
"""

from modules.mqtt.core.base import MQTTMessageHandler
from modules.mqtt.messages import CommandMessage
from core.ipc.message import CommandMessage as IPCCommandMessage, MessageType
from core.ipc.registry import ProcessName


class CommandAudioHandler(MQTTMessageHandler):
    """音频控制指令处理器（远程喊话）
    {
        "device_id": "VIGIDOOR_7c3a41081017190d_RPI",
        "version": "1.0",
        "msg_id": "c2284dcd-724f-4f19-b5b4-8b6aced73006",
        "timestamp": 1773047770813,
        "data": {
            "action": "initiate_call",
            "params": {
                "websocket_url": "ws://localhost:5002"
            }
        }
    }
    """
    
    def can_handle(self, topic: str, message: CommandMessage) -> bool:
        return "/command/audio" in topic
    
    def handle(self, topic: str, message: CommandMessage) -> bool:
        """
        处理音频控制指令
        
        支持的动作：
        - initiate_call: 开始远程喊话
        - terminate_call: 结束远程喊话
        """
        try:
            data = getattr(message, 'data', {}) or {}
            action = data.get('action')
            params = data.get('params', {})
            self.logger.info(f"📥 收到音频控制指令: {action}, params: {params}")

            if action == 'initiate_call':
                audio_msg = IPCCommandMessage(
                    cmd_type=MessageType.CMD_INITIATE_CALL,
                    target=ProcessName.AUDIO_PROCESSOR,
                    cmd_data=params
                )
                self.ipc.send_message(audio_msg)
                self.send_response('audio', message.msg_id, 'success', '已开始远程喊话')
                return True
            elif action == 'terminate_call':
                audio_msg = IPCCommandMessage(
                    cmd_type=MessageType.CMD_TERMINATE_CALL,
                    target=ProcessName.AUDIO_PROCESSOR,
                    cmd_data=params
                )
                self.ipc.send_message(audio_msg)
                self.send_response('audio', message.msg_id, 'success', '已结束远程喊话')
                return True
            else:
                self.logger.warning(f"未知的音频指令: {action}")
                self.send_response('audio', message.msg_id, 'failed', 
                                 f'未知的指令: {action}', error_code=1000)
                return False
        except Exception as e:
            self.logger.error(f"处理音频指令失败: {e}", exc_info=True)
            self.send_response('audio', message.msg_id, 'failed', 
                             str(e), error_code=5000)
            return False
