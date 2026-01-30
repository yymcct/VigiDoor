"""Supervisor message router."""

from core.ipc.message import MessageType, IPCMessage
from .handlers import handle_heartbeat, handle_alarm_intrusion, handle_mqtt_command
from .handlers import SupervisorHandlerContext


class MessageRouter:
    """Route IPC messages to supervisor handlers."""

    def __init__(self, ctx: SupervisorHandlerContext):
        self._ctx = ctx
        self._logger = ctx.logger
        self._route_map = {
            MessageType.HEARTBEAT: handle_heartbeat,
            'heartbeat': handle_heartbeat,
            MessageType.ALARM_INTRUSION: handle_alarm_intrusion,
            MessageType.MQTT_COMMAND: handle_mqtt_command,
            'mqtt_command': handle_mqtt_command,
        }

    def dispatch(self, msg: IPCMessage) -> None:
        msg_type = msg.msg_type
        handler = self._route_map.get(msg_type)
        if handler:
            handler(self._ctx, msg)
        else:
            self._logger.debug(f"未处理的消息类型: {msg_type}")
