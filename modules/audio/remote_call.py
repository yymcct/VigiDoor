"""
远程喊话 WebSocket 客户端（socket.io）
负责会话建立和音频数据接收。

`audio_data` 事件兼容两种格式：
1) 直接二进制: bytes / bytearray / memoryview
2) 字典结构: {
       'audio': bytes,
       'mime_type': 'audio/webm;codecs=opus',
       'timestamp': 1730000000000,
       'session_id': 'xxx',
       'device_id': 'xxx',
       'source': 'browser',
   }
"""

from dataclasses import dataclass
from typing import Callable, Optional, Any
import socketio
from utils.logger import setup_logger

logger = setup_logger('remote_call')


@dataclass
class AudioPacket:
    """结构化音频包，便于记录 metadata 和后续扩展。"""

    audio: bytes
    mime_type: str = "application/octet-stream"
    timestamp: int = 0
    session_id: str = ""
    device_id: str = ""
    source: str = ""


class RemoteCallClient:
    """
    远程喊话客户端

    仅负责连接和接收音频数据，不做解码和播放。
    """

    def __init__(self, on_audio_packet: Callable[[bytes], None]):
        self._on_audio_packet = on_audio_packet
        self._sio = socketio.Client(logger=False, engineio_logger=False)
        self._connected = False
        self._packet_count = 0
        self._register_events()

    def _register_events(self) -> None:
        @self._sio.event
        def connect():
            self._connected = True
            logger.info("远程喊话已连接")

        @self._sio.event
        def disconnect():
            self._connected = False
            logger.info("远程喊话已断开")

        @self._sio.event
        def server_ready(data):
            logger.info(f"服务器就绪: {data}")

        @self._sio.event
        def joined(data):
            logger.info(f"已加入会话: {data}")

        @self._sio.event
        def call_established(data):
            logger.info(f"通话已建立: {data}")

        @self._sio.event
        def audio_data(data):
            try:
                packet = self._parse_audio_packet(data)
                if not packet:
                    return

                self._packet_count += 1
                if self._packet_count == 1 or self._packet_count % 50 == 0:
                    logger.info(
                        "接收音频包: #%s size=%sB mime=%s session=%s source=%s ts=%s",
                        self._packet_count,
                        len(packet.audio),
                        packet.mime_type,
                        packet.session_id or '-',
                        packet.source or '-',
                        packet.timestamp,
                    )

                self._on_audio_packet(packet.audio)
            except Exception as exc:
                logger.error(f"处理音频数据失败: {exc}")

        @self._sio.event
        def peer_disconnected(data):
            logger.warning(f"对方已断开: {data}")

        @self._sio.event
        def peer_hangup(data):
            logger.warning(f"对方已挂断: {data}")

        @self._sio.event
        def call_terminated(data):
            logger.warning(f"通话已终止: {data}")

        @self._sio.event
        def error(data):
            logger.error(f"远程喊话错误: {data}")

    def connect(self, server_url: str, device_id: str, session_id: Optional[str] = None) -> bool:
        if self._connected:
            logger.info("远程喊话已连接，跳过重复连接")
            return True

        if not server_url:
            logger.error("远程喊话连接地址为空")
            return False

        session_id = session_id or device_id

        try:
            logger.info(f"正在连接远程喊话服务器: {server_url}")
            self._sio.connect(server_url)
            self._sio.emit('device_join', {
                'device_id': device_id,
                'session_id': session_id
            })
            return True
        except Exception as exc:
            logger.error(f"远程喊话连接失败: {exc}")
            return False

    def disconnect(self) -> None:
        if not self._connected:
            return
        try:
            self._sio.disconnect()
        except Exception as exc:
            logger.error(f"断开远程喊话失败: {exc}")

    def is_connected(self) -> bool:
        return self._connected

    def _parse_audio_packet(self, data: Any) -> Optional[AudioPacket]:
        if data is None:
            return None

        if isinstance(data, (bytes, bytearray, memoryview)):
            audio = bytes(data)
            return AudioPacket(audio=audio) if audio else None

        if isinstance(data, dict):
            audio = self._extract_audio_bytes(data.get('audio'))
            if not audio:
                logger.debug(
                    "audio_data 缺少有效音频字段: keys=%s",
                    list(data.keys()),
                )
                return None

            return AudioPacket(
                audio=audio,
                mime_type=str(data.get('mime_type') or 'application/octet-stream'),
                timestamp=self._safe_int(data.get('timestamp')),
                session_id=str(data.get('session_id') or ''),
                device_id=str(data.get('device_id') or ''),
                source=str(data.get('source') or ''),
            )

        logger.debug(f"未知音频数据格式: {type(data)}")
        return None

    @staticmethod
    def _extract_audio_bytes(audio_field: Any) -> Optional[bytes]:
        if isinstance(audio_field, (bytes, bytearray, memoryview)):
            audio = bytes(audio_field)
            return audio if audio else None
        return None

    @staticmethod
    def _safe_int(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
