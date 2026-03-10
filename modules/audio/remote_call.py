"""
远程喊话 WebSocket 客户端（socket.io）
负责会话建立和音频数据接收
"""

from typing import Callable, Optional, Any
import socketio
from utils.logger import setup_logger

logger = setup_logger('remote_call')


class RemoteCallClient:
    """
    远程喊话客户端

    仅负责连接和接收音频数据，不做解码和播放。
    """

    def __init__(self, on_audio_packet: Callable[[bytes], None]):
        self._on_audio_packet = on_audio_packet
        self._sio = socketio.Client(logger=False, engineio_logger=False)
        self._connected = False
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
                audio_payload = self._extract_audio_payload(data)
                if audio_payload:
                    self._on_audio_packet(audio_payload)
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

    def _extract_audio_payload(self, data: Any) -> Optional[bytes]:
        if data is None:
            return None

        if isinstance(data, (bytes, bytearray, memoryview)):
            return bytes(data)

        if isinstance(data, dict):
            audio_field = data.get('audio')
            if isinstance(audio_field, (bytes, bytearray, memoryview)):
                return bytes(audio_field)

        logger.debug(f"未知音频数据格式: {type(data)}")
        return None
