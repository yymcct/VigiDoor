"""
安防控制指令处理器（布防/撤防）
"""

from modules.mqtt.core.base import MQTTMessageHandler
from modules.mqtt.messages import CommandMessage
from core.ipc.message import CommandMessage as IPCCommandMessage, MessageType
from core.ipc.registry import ProcessName


class CommandSecurityHandler(MQTTMessageHandler):
    """布防/撤防指令处理器

    MQTT 指令格式：
    {
        "device_id": "VIGIDOOR_xxx",
        "msg_id": "...",
        "data": {
            "action": "arm"    // 或 "disarm"
        }
    }

    发布话题：vigidoor/down/{device_id}/command/security
    """

    def can_handle(self, topic: str, message: CommandMessage) -> bool:
        return "/command/security" in topic

    def handle(self, topic: str, message: CommandMessage) -> bool:
        data = getattr(message, 'data', {}) or {}
        action = data.get('action')
        self.logger.info(f"📥 收到安防控制指令: {action}")

        try:
            if action == 'arm':
                ipc_msg = IPCCommandMessage(
                    cmd_type=MessageType.CMD_ARM,
                    target=ProcessName.SUPERVISOR,
                    cmd_data={}
                )
                self.ipc.send_message(ipc_msg)
                self.send_response('security', message.msg_id, 'success', '布防指令已接收')
                return True

            elif action == 'disarm':
                ipc_msg = IPCCommandMessage(
                    cmd_type=MessageType.CMD_DISARM,
                    target=ProcessName.SUPERVISOR,
                    cmd_data={}
                )
                self.ipc.send_message(ipc_msg)
                self.send_response('security', message.msg_id, 'success', '撤防指令已接收')
                return True

            else:
                self.logger.warning(f"未知的安防指令: {action}")
                self.send_response('security', message.msg_id, 'failed',
                                   f'未知的指令: {action}', error_code=1000)
                return False

        except Exception as e:
            self.logger.error(f"处理安防指令失败: {e}", exc_info=True)
            self.send_response('security', message.msg_id, 'failed',
                               str(e), error_code=5000)
            return False
