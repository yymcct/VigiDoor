"""Supervisor message router."""

from core.ipc.message import MessageType, IPCMessage
from .handlers import handle_heartbeat, handle_alarm_intrusion, handle_audio_anomaly, handle_mqtt_command
from .handlers import handle_arm, handle_disarm
from .handlers import handle_alert_trigger
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
            MessageType.AUDIO_ANOMALY: handle_audio_anomaly,
            MessageType.MQTT_COMMAND: handle_mqtt_command,
            'mqtt_command': handle_mqtt_command,
            MessageType.CMD_ARM: handle_arm,
            MessageType.CMD_DISARM: handle_disarm,
            MessageType.ALERT_TRIGGER: handle_alert_trigger,
        }

    def dispatch(self, msg: IPCMessage) -> None:
        msg_type = msg.msg_type
        handler = self._route_map.get(msg_type)
        if handler:
            handler(self._ctx, msg)
        else:
            self._logger.debug(f"未处理的消息类型: {msg_type}")
