"""Alarm intrusion message handler."""

import time
from typing import Any, Dict

from core.ipc.message import MessageType, IPCMessage, CommandMessage, create_message
from core.ipc.registry import ProcessName
from .context import SupervisorHandlerContext


def handle_alarm_intrusion(ctx: SupervisorHandlerContext, msg: IPCMessage) -> None:
    """处理 AI 检测到的异常"""
    data: Dict[str, Any] = msg.data or {}
    ctx.logger.warning(f"🚨 检测到异常: {data}")

    _set_global_state(ctx, 'alarm')
    _set_alarm_auto_reset(ctx)

    alarm_msg = create_message(
        msg_type=MessageType.ALARM_INTRUSION,
        target=ProcessName.MQTT_CLIENT,
        data=data
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


def _set_alarm_auto_reset(ctx: SupervisorHandlerContext) -> None:
    """设置报警自动恢复时间"""
    reset_seconds = float(ctx.shared_state.get('alarm_auto_reset_seconds', 0) or 0)
    if reset_seconds > 0:
        ctx.shared_state['alarm_until'] = time.time() + reset_seconds
        ctx.logger.info(f"⏱️ 报警自动恢复计时启动: {reset_seconds:.0f}s")
    else:
        ctx.shared_state['alarm_until'] = 0
