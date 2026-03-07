"""
语音会话管理器
管理浏览器和树莓派之间的WebSocket会话状态
"""
import logging
import time
import threading
from typing import Dict, Optional, Set
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ClientType(Enum):
    """客户端类型"""
    BROWSER = "browser"     # 浏览器端
    DEVICE = "device"       # 设备端（树莓派）


class SessionStatus(Enum):
    """会话状态"""
    WAITING = "waiting"           # 等待双方连接
    CONNECTED = "connected"       # 双方已连接，通话中
    DISCONNECTING = "disconnecting"  # 正在断开
    CLOSED = "closed"             # 已关闭


@dataclass
class VoiceSession:
    """语音会话"""
    session_id: str                    # 会话ID（通常使用device_id）
    device_id: str                     # 设备ID
    status: SessionStatus = SessionStatus.WAITING
    
    # 连接的客户端 SID（SocketIO Session ID）
    browser_sid: Optional[str] = None
    device_sid: Optional[str] = None
    
    # 时间戳
    created_at: float = field(default_factory=time.time)
    connected_at: Optional[float] = None
    closed_at: Optional[float] = None
    
    # 统计信息
    browser_messages: int = 0
    device_messages: int = 0
    
    def is_both_connected(self) -> bool:
        """检查双方是否都已连接"""
        return self.browser_sid is not None and self.device_sid is not None
    
    def is_expired(self, timeout: int) -> bool:
        """检查会话是否超时（单方连接超时或等待连接超时）"""
        if self.status == SessionStatus.CLOSED:
            return False
        
        current_time = time.time()
        elapsed = current_time - self.created_at
        
        # 如果双方都连接，不检查超时（由心跳机制处理）
        if self.is_both_connected():
            return False
        
        # 如果只有一方连接或都未连接，检查是否超过超时时间
        return elapsed > timeout
    
    def get_peer_sid(self, client_type: ClientType) -> Optional[str]:
        """获取对端的 SID"""
        if client_type == ClientType.BROWSER:
            return self.device_sid
        else:
            return self.browser_sid
    
    def connect_client(self, client_type: ClientType, sid: str) -> bool:
        """
        连接客户端
        返回是否成功（如果该类型客户端已连接，返回False）
        """
        if client_type == ClientType.BROWSER:
            if self.browser_sid is not None:
                logger.warning(f"会话 {self.session_id} 的浏览器端已连接")
                return False
            self.browser_sid = sid
        else:
            if self.device_sid is not None:
                logger.warning(f"会话 {self.session_id} 的设备端已连接")
                return False
            self.device_sid = sid
        
        # 检查双方是否都已连接
        if self.is_both_connected():
            self.status = SessionStatus.CONNECTED
            self.connected_at = time.time()
            logger.info(f"会话 {self.session_id} 双方已连接，建立通话")
        
        return True
    
    def disconnect_client(self, client_type: ClientType):
        """断开客户端"""
        if client_type == ClientType.BROWSER:
            self.browser_sid = None
        else:
            self.device_sid = None
        
        # 如果任一方断开，标记会话为断开中
        if self.status == SessionStatus.CONNECTED:
            self.status = SessionStatus.DISCONNECTING


class VoiceSessionManager:
    """
    语音会话管理器（单例）
    线程安全的会话管理
    """
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(VoiceSessionManager, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self.sessions: Dict[str, VoiceSession] = {}  # session_id -> VoiceSession
        self.sid_to_session: Dict[str, str] = {}     # client_sid -> session_id
        self._sessions_lock = threading.RLock()
        
        logger.info("VoiceSessionManager 初始化")
    
    def create_session(self, device_id: str) -> VoiceSession:
        """
        创建新会话
        如果设备已有活跃会话，返回已有会话
        """
        with self._sessions_lock:
            # 检查是否已有该设备的活跃会话
            existing_session = self.get_session_by_device(device_id)
            if existing_session and existing_session.status != SessionStatus.CLOSED:
                logger.info(f"设备 {device_id} 已有活跃会话 {existing_session.session_id}")
                return existing_session
            
            # 创建新会话
            session_id = device_id  # 使用 device_id 作为 session_id
            session = VoiceSession(
                session_id=session_id,
                device_id=device_id,
            )
            
            self.sessions[session_id] = session
            logger.info(f"创建新会话: {session_id}, 设备: {device_id}")
            return session
    
    def get_session(self, session_id: str) -> Optional[VoiceSession]:
        """根据会话ID获取会话"""
        with self._sessions_lock:
            return self.sessions.get(session_id)
    
    def get_session_by_sid(self, sid: str) -> Optional[VoiceSession]:
        """根据客户端SID获取会话"""
        with self._sessions_lock:
            session_id = self.sid_to_session.get(sid)
            if session_id:
                return self.sessions.get(session_id)
            return None
    
    def get_session_by_device(self, device_id: str) -> Optional[VoiceSession]:
        """根据设备ID获取会话"""
        with self._sessions_lock:
            # device_id 即为 session_id
            return self.sessions.get(device_id)
    
    def connect_client(
        self, 
        session_id: str, 
        client_type: ClientType, 
        sid: str
    ) -> bool:
        """
        将客户端连接到会话
        返回是否连接成功
        """
        with self._sessions_lock:
            session = self.sessions.get(session_id)
            if not session:
                logger.error(f"会话 {session_id} 不存在")
                return False
            
            success = session.connect_client(client_type, sid)
            if success:
                self.sid_to_session[sid] = session_id
                logger.info(
                    f"客户端 {client_type.value} (SID: {sid[:8]}...) "
                    f"已连接到会话 {session_id}"
                )
            return success
    
    def disconnect_client(self, sid: str) -> Optional[VoiceSession]:
        """
        断开客户端连接
        返回受影响的会话
        """
        with self._sessions_lock:
            session_id = self.sid_to_session.get(sid)
            if not session_id:
                logger.warning(f"未找到 SID {sid[:8]}... 对应的会话")
                return None
            
            session = self.sessions.get(session_id)
            if not session:
                return None
            
            # 判断客户端类型
            if session.browser_sid == sid:
                client_type = ClientType.BROWSER
            elif session.device_sid == sid:
                client_type = ClientType.DEVICE
            else:
                logger.warning(f"SID {sid[:8]}... 不属于会话 {session_id}")
                return None
            
            session.disconnect_client(client_type)
            del self.sid_to_session[sid]
            
            logger.info(
                f"客户端 {client_type.value} (SID: {sid[:8]}...) "
                f"已从会话 {session_id} 断开"
            )
            
            return session
    
    def close_session(self, session_id: str):
        """关闭并清理会话"""
        with self._sessions_lock:
            session = self.sessions.get(session_id)
            if not session:
                return
            
            # 清理 SID 映射
            if session.browser_sid:
                self.sid_to_session.pop(session.browser_sid, None)
            if session.device_sid:
                self.sid_to_session.pop(session.device_sid, None)
            
            # 标记会话为已关闭
            session.status = SessionStatus.CLOSED
            session.closed_at = time.time()
            
            # 删除会话
            del self.sessions[session_id]
            
            logger.info(
                f"会话 {session_id} 已关闭 - "
                f"浏览器消息: {session.browser_messages}, "
                f"设备消息: {session.device_messages}"
            )
    
    def cleanup_expired_sessions(self, timeout: int):
        """清理超时的会话"""
        with self._sessions_lock:
            expired_sessions = []
            
            for session_id, session in self.sessions.items():
                if session.is_expired(timeout):
                    expired_sessions.append(session_id)
            
            for session_id in expired_sessions:
                logger.warning(f"会话 {session_id} 超时，正在清理")
                self.close_session(session_id)
            
            return len(expired_sessions)
    
    def get_active_sessions_count(self) -> int:
        """获取活跃会话数量"""
        with self._sessions_lock:
            return len([s for s in self.sessions.values() 
                       if s.status != SessionStatus.CLOSED])
    
    def get_all_sessions_info(self) -> list:
        """获取所有会话信息（调试用）"""
        with self._sessions_lock:
            return [
                {
                    "session_id": s.session_id,
                    "device_id": s.device_id,
                    "status": s.status.value,
                    "browser_connected": s.browser_sid is not None,
                    "device_connected": s.device_sid is not None,
                    "created_at": s.created_at,
                    "browser_messages": s.browser_messages,
                    "device_messages": s.device_messages,
                }
                for s in self.sessions.values()
            ]


# 全局单例
session_manager = VoiceSessionManager()
