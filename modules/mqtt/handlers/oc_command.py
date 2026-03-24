"""
华为云 IoT OC 命令处理器
"""

import logging
from typing import Optional
from core.state import StateKey


class OcCommandHandler:
    """
    华为云 IoT OC 协议命令处理器

    Topic 格式: $oc/devices/{device_id}/sys/commands/request_id={request_id}
    消息格式:
    {
        "object_device_id": "...",
        "command_name": "GET_STATUS",
        "service_id": "vigidoor",
        "paras": {}
    }
    """

    def __init__(self, state, publisher, logger: Optional[logging.Logger] = None):
        self.state = state
        self.publisher = publisher
        self.logger = logger or logging.getLogger(__name__)

    def handle(self, topic: str, body: dict) -> None:
        try:
            request_id = topic.split('request_id=')[-1]
            command_name = body.get('command_name', '')
            service_id = body.get('service_id', '')
            self.logger.info(
                f"📥 收到 OC 命令: service_id={service_id}, command_name={command_name}, request_id={request_id}"
            )

            if command_name == 'GET_STATUS':
                is_armed = bool(self.state.get(StateKey.IS_ARMED, False))
                self.publisher.publish_oc_command_response(
                    request_id=request_id,
                    result_code=0,
                    response_name='COMMAND_RESPONSE',
                    paras={'is_armed': is_armed}
                )
                self.logger.info(f"📤 GET_STATUS 响应已发送: is_armed={is_armed}")
            else:
                self.logger.warning(f"未知的 OC 命令: {command_name}")
                self.publisher.publish_oc_command_response(
                    request_id=request_id,
                    result_code=1,
                    response_name='COMMAND_RESPONSE',
                    paras={'error': f'unknown command: {command_name}'}
                )

        except Exception as e:
            self.logger.error(f"处理 OC 命令失败: {e}", exc_info=True)
