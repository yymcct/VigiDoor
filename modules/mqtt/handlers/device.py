"""
设备控制指令处理器
"""

from modules.mqtt.core.base import MQTTMessageHandler
from modules.mqtt.messages import CommandMessage


class CommandDeviceHandler(MQTTMessageHandler):
    """设备控制指令处理器"""
    
    def can_handle(self, topic: str, message: CommandMessage) -> bool:
        return "/command/device" in topic
    
    def handle(self, topic: str, message: CommandMessage) -> bool:
        """
        处理设备控制指令
        
        支持的动作：
        - reboot: 重启设备
        """
        action = message.get_action()
        self.logger.info(f"📥 收到设备控制指令: {action}")
        
        try:
            if action == 'reboot':
                # 重启设备
                delay = message.data.get('delay', 5)
                self.send_response('device', message.msg_id, 'success', 
                                 f'设备将在 {delay} 秒后重启')
                # TODO: 实现重启逻辑
                
            else:
                self.logger.warning(f"未知的设备指令: {action}")
                self.send_response('device', message.msg_id, 'failed', 
                                 f'未知的指令: {action}', error_code=1000)
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"处理设备指令失败: {e}", exc_info=True)
            self.send_response('device', message.msg_id, 'failed', 
                             str(e), error_code=5000)
            return False
