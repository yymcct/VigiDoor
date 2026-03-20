"""布防/撤防消息处理器。"""

import time
from core.ipc.message import MessageType, IPCMessage, CommandMessage
from core.ipc.registry import ProcessName
from .context import SupervisorHandlerContext


def handle_arm(ctx: SupervisorHandlerContext, msg: IPCMessage) -> None:
    """处理布防指令"""
    was_armed = ctx.shared_state.get('is_armed', True)
    ctx.shared_state['is_armed'] = True #TODO is_armed 改成枚举状态
    ctx.logger.info(f"🔒 布防: {'已是布防，重复确认' if was_armed else '撤防 → 布防'}")

    ctx.message_bus.send(ProcessName.AUDIO_PROCESSOR, CommandMessage(
        cmd_type=MessageType.CMD_PLAY_AUDIO,
        target=ProcessName.AUDIO_PROCESSOR,
        cmd_data={'path': 'assets/audio/armed.mp3'}
    ))

    ctx.message_bus.send(ProcessName.MQTT_CLIENT, CommandMessage(
        cmd_type=MessageType.STATUS_SECURITY,
        target=ProcessName.MQTT_CLIENT,
        cmd_data={'status': 'armed', 'timestamp': int(time.time() * 1000)}
    ))


def handle_disarm(ctx: SupervisorHandlerContext, msg: IPCMessage) -> None:
    """处理撤防指令"""
    was_armed = ctx.shared_state.get('is_armed', True)
    ctx.shared_state['is_armed'] = False
    ctx.logger.info(f"🔓 撤防: {'布防 → 撤防' if was_armed else '已是撤防，重复确认'}")

    ctx.message_bus.send(ProcessName.AUDIO_PROCESSOR, CommandMessage(
        cmd_type=MessageType.CMD_PLAY_AUDIO,
        target=ProcessName.AUDIO_PROCESSOR,
        cmd_data={'path': 'assets/audio/disarmed.mp3'}
    ))

    ctx.message_bus.send(ProcessName.MQTT_CLIENT, CommandMessage(
        cmd_type=MessageType.STATUS_SECURITY,
        target=ProcessName.MQTT_CLIENT,
        cmd_data={'status': 'disarmed', 'timestamp': int(time.time() * 1000)}
    ))
 
