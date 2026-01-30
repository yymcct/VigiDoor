"""Heartbeat message handler."""

from time import time as _now

from core.ipc.message import IPCMessage
from .context import SupervisorHandlerContext


def handle_heartbeat(ctx: SupervisorHandlerContext, msg: IPCMessage) -> None:
    """处理心跳消息"""
    process_name = msg.sender
    if process_name:
        ctx.shared_state['last_heartbeat'][process_name] = _now()
        ctx.logger.debug(f"收到 {process_name} 心跳")
