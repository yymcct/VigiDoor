"""
摩西尔 OLED 屏幕设备实现

通过 HTTP API 控制摩西尔 OLED 屏幕播放节目。
API base url: http://<ip>:<port>
"""

import json
import uuid
import socket
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Any, List, Optional

from ..base import OutputDevice
from utils.logger import setup_logger

logger = setup_logger('mosier_oled')


# ─────────────────────────────────────────────
# 数据实体
# ─────────────────────────────────────────────

@dataclass
class PreviewInfo:
    """节目预览图信息"""
    path: str
    name: str
    original_name: str
    engine: int
    size: int
    location: str
    type: str

    @classmethod
    def from_dict(cls, d: dict) -> 'PreviewInfo':
        return cls(
            path=d.get('path', ''),
            name=d.get('name', ''),
            original_name=d.get('originalName', ''),
            engine=int(d.get('engine', 0)),
            size=int(d.get('size', 0)),
            location=d.get('location', ''),
            type=d.get('type', ''),
        )


@dataclass
class PlayMode:
    """播放模式"""
    mode: str
    cycle: int
    duration: int

    @classmethod
    def from_dict(cls, d: dict) -> 'PlayMode':
        return cls(
            mode=d.get('mode', 'duration'),
            cycle=int(d.get('cycle', 1)),
            duration=int(d.get('duration', 10000)),
        )


@dataclass
class MaterialFile:
    """素材文件"""
    path: str
    name: str
    original_name: str
    meta: str
    engine: int
    size: int
    location: str
    type: str

    @classmethod
    def from_dict(cls, d: dict) -> 'MaterialFile':
        return cls(
            path=d.get('path', ''),
            name=d.get('name', ''),
            original_name=d.get('originalName', ''),
            meta=d.get('meta', ''),
            engine=int(d.get('engine', 0)),
            size=int(d.get('size', 0)),
            location=d.get('location', ''),
            type=d.get('type', ''),
        )


@dataclass
class Material:
    """窗口素材"""
    id: str
    window_id: str
    name: str
    type: str
    play_mode: PlayMode
    meta: str
    index: int
    files: List[MaterialFile] = field(default_factory=list)
    extra: str = ''

    @classmethod
    def from_dict(cls, d: dict) -> 'Material':
        return cls(
            id=d.get('id', ''),
            window_id=d.get('windowId', ''),
            name=d.get('name', ''),
            type=d.get('type', ''),
            play_mode=PlayMode.from_dict(d.get('playMode', {})),
            meta=d.get('meta', ''),
            index=int(d.get('index', 0)),
            files=[MaterialFile.from_dict(f) for f in d.get('files', [])],
            extra=d.get('extra', ''),
        )


@dataclass
class Window:
    """节目页窗口"""
    id: str
    page_id: str
    name: str
    type: str
    index: int
    left: int
    top: int
    width: int
    height: int
    rotation: int
    extra: str
    material_list: List[Material] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> 'Window':
        return cls(
            id=d.get('id', ''),
            page_id=d.get('pageId', ''),
            name=d.get('name', ''),
            type=d.get('type', ''),
            index=int(d.get('index', 0)),
            left=int(d.get('left', 0)),
            top=int(d.get('top', 0)),
            width=int(d.get('width', 0)),
            height=int(d.get('height', 0)),
            rotation=int(d.get('rotation', 0)),
            extra=d.get('extra', ''),
            material_list=[Material.from_dict(m) for m in d.get('materialList', [])],
        )


@dataclass
class Page:
    """节目页"""
    id: str
    program_id: str
    name: str
    index: int
    play_mode: PlayMode
    window_list: List[Window] = field(default_factory=list)
    extra: str = ''

    @classmethod
    def from_dict(cls, d: dict) -> 'Page':
        return cls(
            id=d.get('id', ''),
            program_id=d.get('programId', ''),
            name=d.get('name', ''),
            index=int(d.get('index', 0)),
            play_mode=PlayMode.from_dict(d.get('playMode', {})),
            window_list=[Window.from_dict(w) for w in d.get('windowList', [])],
            extra=d.get('extra', ''),
        )


@dataclass
class Program:
    """节目"""
    id: str
    name: str
    width: int
    height: int
    source: str
    valid_time_type: str
    version: int = 0
    preview: Optional[PreviewInfo] = None
    create_user_id: str = ''
    page_list: List[Page] = field(default_factory=list)
    extra: str = ''

    @classmethod
    def from_dict(cls, d: dict) -> 'Program':
        preview_raw = d.get('preview')
        return cls(
            id=d.get('id', ''),
            name=d.get('name', ''),
            width=int(d.get('width', 0)),
            height=int(d.get('height', 0)),
            source=d.get('source', ''),
            valid_time_type=d.get('validTimeType', ''),
            version=int(d.get('version', 0)),
            preview=PreviewInfo.from_dict(preview_raw) if preview_raw else None,
            create_user_id=d.get('createUserId', ''),
            page_list=[Page.from_dict(p) for p in d.get('pageList', [])],
            extra=d.get('extra', ''),
        )


# ─────────────────────────────────────────────
# 设备类
# ─────────────────────────────────────────────

class MosierOLEDDevice(OutputDevice):
    """
    摩西尔 OLED 屏幕设备

    通过 HTTP API 控制屏幕播放节目。
    """

    def __init__(
        self,
        ip: str,
        port: int = 8080,
        timeout: int = 5,
    ):
        """
        初始化摩西尔 OLED 屏幕设备

        Args:
            ip: 设备 IP 地址
            port: HTTP 端口，默认 8080
            timeout: HTTP 超时秒数，默认 5
        """
        super().__init__(
            device_id='mosier_oled',
            device_type='oled',
            name='摩西尔OLED屏幕',
        )
        self.ip = ip
        self.port = port
        self.timeout = timeout
        self._base_url = f'http://{ip}:{port}'

    # ──────────────── OutputDevice 接口 ────────────────

    def initialize(self) -> bool:
        """初始化设备：验证连通性"""
        try:
            programs = self.get_all_programs()
            logger.info(
                f'✅ 摩西尔 OLED 初始化成功，当前节目数: {len(programs)} [{self._base_url}]'
            )
            self._initialized = True
            return True
        except Exception as e:
            logger.error(f'摩西尔 OLED 初始化失败（{self._base_url}）: {e}')
            self._initialized = False
            return False

    def cleanup(self) -> None:
        """清理资源：停止播放"""
        try:
            self.stop()
        except Exception:
            pass

    def write(self, data: Any) -> bool:
        """
        写入（播放）节目

        Args:
            data: 节目名称（str）或节目 ID（str，以 PG 开头）

        Returns:
            bool: 成功返回 True
        """
        if isinstance(data, str):
            # 以 "PG" 开头视为直接 ID 播放
            if data.startswith('PG'):
                return self.play(data)
            return self.play_by_name(data)
        logger.warning(f'MosierOLEDDevice.write() 收到不支持的数据类型: {type(data)}')
        return False

    def update(self) -> None:
        """无需周期性更新（屏幕自主播放）"""
        pass

    # ──────────────── 核心 HTTP 方法 ────────────────

    def _send_cmd(
        self,
        cmd: str,
        value_json: Optional[dict] = None,
    ) -> dict:
        """
        向设备发送 HTTP 指令

        Args:
            cmd: 指令名称，如 "program-start"
            value_json: 指令参数字典，可为 None

        Returns:
            dict: 响应的 message 对象

        Raises:
            urllib.error.URLError: 网络错误
            ValueError: 响应体解析失败或 ret != 0
        """
        message: dict = {'cmd': cmd}
        if value_json is not None:
            message['valueJson'] = value_json

        payload = {
            'type': 'cmd',
            'reqId': uuid.uuid4().hex,
            'message': message,
        }

        body = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            url=f'{self._base_url}/v1/cmd',
            data=body,
            headers={'Content-Type': 'application/json'},
            method='POST',
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
        except socket.timeout as e:
            raise urllib.error.URLError(f'请求超时（{self.timeout}s）') from e

        try:
            result = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f'响应 JSON 解析失败: {raw!r}') from e

        ret = result.get('ret', -1)
        if ret != 0:
            err = result.get('error', '未知错误')
            raise ValueError(f'指令 {cmd} 返回错误 (ret={ret}): {err}')

        return result

    # ──────────────── 节目操作 ────────────────

    def get_all_programs(self) -> List[Program]:
        """
        获取设备上的所有节目

        Returns:
            List[Program]: 节目列表
        """
        msg = self._send_cmd('program-getAllProgram')
        data = msg.get('data', {})
        raw_list = data.get('list', [])
        return [Program.from_dict(p) for p in raw_list]

    def play(self, program_id: str) -> bool:
        """
        按节目 ID 播放节目

        Args:
            program_id: 节目 ID

        Returns:
            bool: 成功返回 True
        """
        try:
            self._send_cmd('program-start', {'id': program_id})
            logger.info(f'▶ 播放节目 id={program_id}')
            return True
        except Exception as e:
            logger.error(f'播放节目失败 id={program_id}: {e}')
            return False

    def play_by_name(self, name: str) -> bool:
        """
        按节目名称播放节目（不区分大小写匹配）

        Args:
            name: 节目名称，如 "daily"、"alarm" 等

        Returns:
            bool: 找到并成功播放返回 True，否则返回 False
        """
        try:
            programs = self.get_all_programs()
        except Exception as e:
            logger.error(f'获取节目列表失败: {e}')
            return False

        name_lower = name.lower()
        matched = next(
            (p for p in programs if p.name.lower() == name_lower),
            None,
        )

        if matched is None:
            logger.warning(
                f'未找到名称为 "{name}" 的节目，'
                f'可用节目: {[p.name for p in programs]}'
            )
            return False

        return self.play(matched.id)

    def pause(self) -> bool:
        """暂停播放"""
        try:
            self._send_cmd('program-pause')
            logger.info('⏸ 暂停播放')
            return True
        except Exception as e:
            logger.error(f'暂停播放失败: {e}')
            return False

    def resume(self) -> bool:
        """恢复播放"""
        try:
            self._send_cmd('program-resume')
            logger.info('▶ 恢复播放')
            return True
        except Exception as e:
            logger.error(f'恢复播放失败: {e}')
            return False

    def stop(self) -> bool:
        """停止播放"""
        try:
            self._send_cmd('program-stop')
            logger.info('⏹ 停止播放')
            return True
        except Exception as e:
            logger.error(f'停止播放失败: {e}')
            return False

    def remove(self, program_id: str) -> bool:
        """
        删除指定节目

        Args:
            program_id: 节目 ID

        Returns:
            bool: 成功返回 True
        """
        try:
            self._send_cmd('program-remove', {'id': program_id})
            logger.info(f'🗑 删除节目 id={program_id}')
            return True
        except Exception as e:
            logger.error(f'删除节目失败 id={program_id}: {e}')
            return False

    def remove_all(self) -> bool:
        """清空所有节目"""
        try:
            self._send_cmd('program-removeAll', {})
            logger.info('🗑 清空所有节目')
            return True
        except Exception as e:
            logger.error(f'清空节目失败: {e}')
            return False
