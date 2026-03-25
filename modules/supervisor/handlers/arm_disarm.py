"""布防/撤防消息处理器。"""

import time
from core.ipc.message import MessageType, IPCMessage, CommandMessage
from core.ipc.registry import ProcessName
from core.state import StateKey
from .context import SupervisorHandlerContext


def handle_arm(ctx: SupervisorHandlerContext, msg: IPCMessage) -> None:
    """处理布防指令"""
    was_armed = ctx.shared_state.get(StateKey.IS_ARMED, True)
    ctx.shared_state[StateKey.IS_ARMED] = True
    ctx.logger.info(f"🔒 布防: {'已是布防，重复确认' if was_armed else '撤防 → 布防'}")

    ctx.db_writer.write_arm_disarm(action='arm', source='mqtt')

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

    ctx.message_bus.send(ProcessName.DEVICE_CONTROLLER, CommandMessage(
        cmd_type=MessageType.CMD_SET_LIGHT,
        target=ProcessName.DEVICE_CONTROLLER,
        cmd_data={'mode': 'guard'}
    ))


def handle_disarm(ctx: SupervisorHandlerContext, msg: IPCMessage) -> None:
    """处理撤防指令"""
    was_armed = ctx.shared_state.get(StateKey.IS_ARMED, True)
    ctx.shared_state[StateKey.IS_ARMED] = False
    ctx.logger.info(f"🔓 撤防: {'布防 → 撤防' if was_armed else '已是撤防，重复确认'}")

    
    ctx.db_writer.write_arm_disarm(action='disarm', source='mqtt')

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

    ctx.message_bus.send(ProcessName.DEVICE_CONTROLLER, CommandMessage(
        cmd_type=MessageType.CMD_SET_LIGHT,
        target=ProcessName.DEVICE_CONTROLLER,
        cmd_data={'mode': 'daily'}
    ))
 
