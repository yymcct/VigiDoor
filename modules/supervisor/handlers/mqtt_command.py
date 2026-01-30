"""MQTT command message handler."""

from typing import Any, Dict

from core.ipc.message import MessageType, IPCMessage, CommandMessage
from core.ipc.registry import ProcessName
from .context import SupervisorHandlerContext


def handle_mqtt_command(ctx: SupervisorHandlerContext, msg: IPCMessage) -> None:
    """处理平台下发的指令"""
    data: Dict[str, Any] = msg.data or {}
    action = data.get('action')
    ctx.logger.info(f"📥 收到平台指令: {action}")

    handler_map = {
        'remote_speak': _handle_remote_speak,
    }

    handler = handler_map.get(action)
    if handler:
        handler(ctx, msg)
    else:
        ctx.logger.warning(f"未知的平台指令: {action}")


def _handle_remote_speak(ctx: SupervisorHandlerContext, msg: IPCMessage) -> None:
    """处理远程喊话指令"""
    data: Dict[str, Any] = msg.data or {}
    audio_msg = CommandMessage(
        cmd_type=MessageType.CMD_PLAY_AUDIO,
        target=ProcessName.AUDIO_PROCESSOR,
        cmd_data=data
    )
    ctx.message_bus.send(ProcessName.AUDIO_PROCESSOR, audio_msg)
