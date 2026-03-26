"""Alarm intrusion message handler."""

import time
from typing import Any, Dict

from core.ipc.message import MessageType, IPCMessage, CommandMessage, create_message
from core.ipc.registry import ProcessName
from core.state import GlobalState, StateKey
from .context import SupervisorHandlerContext


def handle_alarm_intrusion(ctx: SupervisorHandlerContext, msg: IPCMessage) -> None:
    """处理 AI 检测到的异常"""
    data: Dict[str, Any] = msg.data or {}
    ctx.logger.warning(f"🚨 检测到异常: {data}")

    _set_global_state(ctx, GlobalState.ALARM)
    _set_alarm_auto_reset(ctx)

    alarm_msg = create_message(
        msg_type=MessageType.ALARM_INTRUSION,
        target=ProcessName.MQTT_CLIENT,
        data=data
    )
    ctx.message_bus.send(ProcessName.MQTT_CLIENT, alarm_msg)

    audio_msg = CommandMessage(
        cmd_type=MessageType.CMD_PLAY_AUDIO,
        target=ProcessName.AUDIO_PROCESSOR,
        cmd_data={
            'path': 'assets/audio/qinglikai.mp3'
        }
    )
    ctx.message_bus.send(ProcessName.AUDIO_PROCESSOR, audio_msg)

    # 通知录像进程给当前片段打上 alarm 标签
    tag_msg = create_message(
        msg_type=MessageType.CMD_TAG_RECORDING,
        target=ProcessName.RECORDER,
        data={"alarm_level": "alarm"}
    )
    ctx.message_bus.send(ProcessName.RECORDER, tag_msg)


def _set_global_state(ctx: SupervisorHandlerContext, state: GlobalState) -> None:
    """设置全局状态"""
    old_state = ctx.shared_state[StateKey.GLOBAL_STATE]
    if old_state != state:
        ctx.shared_state[StateKey.GLOBAL_STATE] = state
        ctx.logger.info(f"🔄 全局状态切换: {old_state} → {state}")


def handle_audio_anomaly(ctx: SupervisorHandlerContext, msg: IPCMessage) -> None:
    """处理音频异常检测"""
    data: Dict[str, Any] = msg.data or {}
    ctx.logger.warning(f"🔊 检测到音频异常: {data}")

    # 计算严重程度
    delta_db = data.get('delta_db', 0)
    if delta_db >= 30:
        severity = 'critical'
    elif delta_db >= 20:
        severity = 'high'
    elif delta_db >= 10:
        severity = 'medium'
    else:
        severity = 'low'

    # 转换为 AlarmIntrusionMessage 格式
    alarm_data = {
        'alarm_type': 'audio_anomaly',
        'source': 'audio',
        'confidence': min(delta_db / 30.0, 1.0),  # 归一化为0-1
        'intrusion_count': 0,
        'severity': severity,
        'snapshot_urls': [],
        'video_urls': [],
        'remark': f"{data.get('event_name', '音量异常')}: 当前{data.get('current_db', 0):.1f}dB, 基线{data.get('baseline_db', 0):.1f}dB, 偏差{delta_db:+.1f}dB"
    }

    # 发送给 MQTT
    alarm_msg = create_message(
        msg_type=MessageType.ALARM_INTRUSION,
        target=ProcessName.MQTT_CLIENT,
        data=alarm_data
    )
    ctx.message_bus.send(ProcessName.MQTT_CLIENT, alarm_msg)

    # 通知录像进程给当前片段打标（音频异常归为 alert 级别）
    tag_msg = create_message(
        msg_type=MessageType.CMD_TAG_RECORDING,
        target=ProcessName.RECORDER,
        data={"alarm_level": "alert"}
    )
    ctx.message_bus.send(ProcessName.RECORDER, tag_msg)

    audio_msg = CommandMessage(
        cmd_type=MessageType.CMD_PLAY_AUDIO,
        target=ProcessName.AUDIO_PROCESSOR,
        cmd_data={
            'path': 'assets/audio/audio_alarm.mp3'
        }
    )
    ctx.message_bus.send(ProcessName.AUDIO_PROCESSOR, audio_msg)
    
    ctx.logger.info(f"✅ 音频异常消息已转发至 MQTT (严重程度: {severity})")


def _set_alarm_auto_reset(ctx: SupervisorHandlerContext) -> None:
    """设置报警自动恢复时间"""
    reset_seconds = float(ctx.shared_state.get(StateKey.ALARM_AUTO_RESET_SECONDS, 0) or 0)
    if reset_seconds > 0:
        ctx.shared_state[StateKey.ALARM_UNTIL] = time.time() + reset_seconds
        ctx.logger.info(f"⏱️ 报警自动恢复计时启动: {reset_seconds:.0f}s")
    else:
        ctx.shared_state[StateKey.ALARM_UNTIL] = 0


def handle_alert_trigger(ctx: SupervisorHandlerContext, msg: IPCMessage) -> None:
    """处理警戒触发（有人出现在画面但未入侵警戒区域）"""
    ctx.logger.info("⚠️ 检测到人员出现，进入警戒状态")
    _set_global_state(ctx, GlobalState.ALERT)
    _set_alert_auto_reset(ctx)


def _set_alert_auto_reset(ctx: SupervisorHandlerContext) -> None:
    """设置警戒自动恢复时间"""
    reset_seconds = float(ctx.shared_state.get(StateKey.ALERT_AUTO_RESET_SECONDS, 0) or 0)
    if reset_seconds > 0:
        ctx.shared_state[StateKey.ALERT_UNTIL] = time.time() + reset_seconds
        ctx.logger.info(f"⏱️ 警戒自动恢复计时启动: {reset_seconds:.0f}s")
    else:
        ctx.shared_state[StateKey.ALERT_UNTIL] = 0
