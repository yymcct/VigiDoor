"""Alarm intrusion message handler."""

from typing import Any, Dict

from core.ipc.message import MessageType, IPCMessage, CommandMessage
from core.ipc.registry import ProcessName
from .context import SupervisorHandlerContext


def handle_alarm_intrusion(ctx: SupervisorHandlerContext, msg: IPCMessage) -> None:
    """处理 AI 检测到的异常"""
    data: Dict[str, Any] = msg.data or {}
    ctx.logger.warning(f"🚨 检测到异常: {data}")

    _set_global_state(ctx, 'alarm')

    alarm_msg = CommandMessage(
        cmd_type=MessageType.REPORT_ALARM,
        target=ProcessName.MQTT_CLIENT,
        cmd_data=data
    )
    ctx.message_bus.send(ProcessName.MQTT_CLIENT, alarm_msg)

    light_msg = CommandMessage(
        cmd_type=MessageType.CMD_SET_LIGHT,
        target=ProcessName.DEVICE_CONTROLLER,
        cmd_data={'mode': 'alarm'}
    )
    ctx.message_bus.send(ProcessName.DEVICE_CONTROLLER, light_msg)


def _set_global_state(ctx: SupervisorHandlerContext, state: str) -> None:
    """设置全局状态"""
    old_state = ctx.shared_state['global_state']
    if old_state != state:
        ctx.shared_state['global_state'] = state
        ctx.logger.info(f"🔄 全局状态切换: {old_state} → {state}")
