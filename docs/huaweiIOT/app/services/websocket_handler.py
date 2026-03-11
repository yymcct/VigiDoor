"""
WebSocket 事件处理器
处理浏览器和设备的 WebSocket 连接、消息转发
"""
import logging
from flask import request
from flask_socketio import SocketIO, emit, join_room, leave_room, disconnect
from app.services.voice_session import (
    session_manager,
    ClientType,
    SessionStatus,
)
from app.config import Config

logger = logging.getLogger(__name__)

# SocketIO 实例将在 app/__init__.py 中初始化
socketio = None


def init_socketio(app):
    """初始化 SocketIO"""
    global socketio

    # Flask-SocketIO 接收不带前导斜杠的 path，客户端使用 /ws 连接

    socketio = SocketIO(
        app,
        cors_allowed_origins="*",  # 生产环境建议配置具体域名
        async_mode='gevent',       # 使用 gevent 异步模式
        path="/ws",
        # Flask 3.x 下禁用 SocketIO 的会话托管，避免 RequestContext.session 赋值报错
        manage_session=False,
        logger=False,
        engineio_logger=False,
        ping_timeout=60,
        ping_interval=25,
    )
    
    # 注册事件处理器
    register_events(socketio)
    
    # 启动后台任务
    socketio.start_background_task(cleanup_expired_sessions_task)
    
    logger.info(
        "SocketIO 初始化完成"
    )
    return socketio


def register_events(sio: SocketIO):
    """注册所有 WebSocket 事件"""
    
    # ==================== 连接事件 ====================
    
    @sio.on('connect')
    def handle_connect():
        """客户端连接事件"""
        sid = request.sid
        logger.info(f"客户端连接: SID={sid[:8]}...")
        emit('server_ready', {'message': '服务器已就绪'})
    
    @sio.on('disconnect')
    def handle_disconnect():
        """客户端断开连接事件"""
        sid = request.sid
        logger.info(f"客户端断开: SID={sid[:8]}...")
        
        # 从会话管理器中移除
        session = session_manager.disconnect_client(sid)
        
        if session:
            # 通知对端
            peer_sid = None
            if session.browser_sid and session.browser_sid != sid:
                peer_sid = session.browser_sid
            elif session.device_sid and session.device_sid != sid:
                peer_sid = session.device_sid
            
            if peer_sid:
                emit(
                    'peer_disconnected',
                    {'message': '对方已断开连接'},
                    to=peer_sid
                )
            
            # 如果双方都断开，关闭会话
            if not session.browser_sid and not session.device_sid:
                session_manager.close_session(session.session_id)
    
    # ==================== 浏览器端事件 ====================
    
    @sio.on('browser_join')
    def handle_browser_join(data):
        """
        浏览器端加入会话
        data: {
            "device_id": "VIGIDOOR_xxx_RPI",
            "session_id": "xxx"  # 可选，通常使用 device_id
        }
        """
        sid = request.sid
        device_id = data.get('device_id')
        session_id = data.get('session_id', device_id)
        
        if not device_id:
            emit('error', {'message': 'device_id 是必填项'})
            return
        
        logger.info(f"浏览器加入会话: device_id={device_id}, SID={sid[:8]}...")
        
        # 获取或创建会话
        session = session_manager.get_session(session_id)
        if not session:
            logger.error(f"会话 {session_id} 不存在")
            emit('error', {'message': f'会话 {session_id} 不存在'})
            return
        
        # 连接客户端到会话
        success = session_manager.connect_client(
            session_id=session_id,
            client_type=ClientType.BROWSER,
            sid=sid
        )
        
        if not success:
            emit('error', {'message': '该会话的浏览器端已连接'})
            return
        
        # 加入 SocketIO 房间
        join_room(session_id)
        
        # 回复加入成功
        emit('joined', {
            'session_id': session_id,
            'device_id': device_id,
            'role': 'browser',
            'waiting_for_device': session.device_sid is None,
        })
        
        # 如果双方都已连接，通知双方建立通话
        if session.is_both_connected():
            emit('call_established', {
                'message': '通话已建立',
                'session_id': session_id,
            }, to=session_id)
    
    # ==================== 设备端事件 ====================
    
    @sio.on('device_join')
    def handle_device_join(data):
        """
        设备端加入会话
        data: {
            "device_id": "VIGIDOOR_xxx_RPI",
            "session_id": "xxx"  # 可选
        }
        """
        sid = request.sid
        device_id = data.get('device_id')
        session_id = data.get('session_id', device_id)
        
        if not device_id:
            emit('error', {'message': 'device_id 是必填项'})
            return
        
        logger.info(f"设备加入会话: device_id={device_id}, SID={sid[:8]}...")
        
        # 获取或创建会话
        session = session_manager.get_session(session_id)
        if not session:
            logger.error(f"会话 {session_id} 不存在")
            emit('error', {'message': f'会话 {session_id} 不存在'})
            return
        
        # 连接客户端到会话
        success = session_manager.connect_client(
            session_id=session_id,
            client_type=ClientType.DEVICE,
            sid=sid
        )
        
        if not success:
            emit('error', {'message': '该会话的设备端已连接'})
            return
        
        # 加入 SocketIO 房间
        join_room(session_id)
        
        # 回复加入成功
        emit('joined', {
            'session_id': session_id,
            'device_id': device_id,
            'role': 'device',
            'waiting_for_browser': session.browser_sid is None,
        })
        
        # 如果双方都已连接，通知双方建立通话
        if session.is_both_connected():
            emit('call_established', {
                'message': '通话已建立',
                'session_id': session_id,
            }, to=session_id)
    
    # ==================== 音频数据转发 ====================
    
    @sio.on('audio_data')
    def handle_audio_data(data):
        """
        音频数据转发
        data: {
            "audio": <binary/base64>,
            "timestamp": 1234567890,
            ... 其他字段
        }
        """
        sid = request.sid
        
        # 获取会话
        session = session_manager.get_session_by_sid(sid)
        if not session:
            logger.warning(f"未找到 SID {sid[:8]}... 对应的会话")
            return
        
        # 判断发送方类型
        if session.browser_sid == sid:
            sender_type = ClientType.BROWSER
            session.browser_messages += 1
        elif session.device_sid == sid:
            sender_type = ClientType.DEVICE
            session.device_messages += 1
        else:
            logger.warning(f"SID {sid[:8]}... 不属于会话 {session.session_id}")
            return
        
        # 获取对端 SID
        peer_sid = session.get_peer_sid(sender_type)
        
        if not peer_sid:
            # 对端未连接，丢弃数据
            if session.browser_messages + session.device_messages == 1:
                # 只在第一次打印警告
                logger.warning(
                    f"会话 {session.session_id} 对端未连接，"
                    f"来自 {sender_type.value} 的数据被丢弃"
                )
            return
        
        # 转发音频数据到对端
        emit('audio_data', data, to=peer_sid)
    
    # ==================== 心跳 ====================
    
    @sio.on('ping')
    def handle_ping():
        """心跳检测"""
        emit('pong')
    
    # ==================== 主动挂断 ====================
    
    @sio.on('hangup')
    def handle_hangup():
        """主动挂断"""
        sid = request.sid
        logger.info(f"客户端主动挂断: SID={sid[:8]}...")
        
        session = session_manager.get_session_by_sid(sid)
        if session:
            # 通知对端
            peer_sid = None
            if session.browser_sid and session.browser_sid != sid:
                peer_sid = session.browser_sid
            elif session.device_sid and session.device_sid != sid:
                peer_sid = session.device_sid
            
            if peer_sid:
                emit('peer_hangup', {'message': '对方已挂断'}, to=peer_sid)
            
            # 关闭会话
            session_manager.close_session(session.session_id)
        
        # 断开连接
        disconnect()


def cleanup_expired_sessions_task():
    """
    后台任务：定期清理超时会话
    """
    while True:
        try:
            # 在 gevent/eventlet 模式下必须使用 socketio.sleep，避免阻塞事件循环
            socketio.sleep(30)  # 每30秒检查一次
            
            timeout = Config.WS_SESSION_TIMEOUT
            cleaned = session_manager.cleanup_expired_sessions(timeout)
            
            if cleaned > 0:
                logger.info(f"清理了 {cleaned} 个超时会话")
        
        except Exception as e:
            logger.exception(f"清理超时会话时出错: {e}")
