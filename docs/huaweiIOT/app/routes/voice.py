"""
语音呼叫路由
提供远程语音通话控制 API
"""
import logging
from flask import Blueprint, request, jsonify
from app.services.voice_session import session_manager, SessionStatus
from app.services.iotda import send_device_command
from app.config import Config

logger = logging.getLogger(__name__)

voice_bp = Blueprint("voice", __name__)


@voice_bp.route("/call/initiate", methods=["POST"])
def initiate_call():
    """
    发起语音呼叫
    
    请求体:
    {
        "device_id": "VIGIDOOR_xxx_RPI"
    }
    
    响应:
    {
        "success": true,
        "session_id": "VIGIDOOR_xxx_RPI",
        "message": "语音呼叫已发起，等待设备响应",
        "websocket_url": "ws://server:5002",
        "device_notified": true
    }
    """
    try:
        data = request.get_json(silent=True) or {}
        
        device_id = data.get("device_id")
        if not device_id:
            return jsonify({
                "success": False,
                "error": "device_id 是必填项"
            }), 400
        
        # 检查并发限制
        active_count = session_manager.get_active_sessions_count()
        if active_count >= Config.MAX_CONCURRENT_SESSIONS:
            return jsonify({
                "success": False,
                "error": "已达到最大并发会话数，请稍后再试"
            }), 503
        
        # 创建会话
        session = session_manager.create_session(device_id)
        
        # 通过 IoTDA 通知设备连接 WebSocket
        command_data = {
            "action": "connect_websocket",
            "session_id": session.session_id,
            "device_id": device_id,
        }
        
        device_notified = False
        iotda_msg_id = None
        
        result = send_device_command(device_id=device_id, message_data=command_data)
        if result.get("success"):
            device_notified = True
            iotda_msg_id = result.get("msg_id")
            logger.info(f"已通过 IoTDA 通知设备 {device_id} 连接 WebSocket")
        else:
            logger.warning(f"通知设备 {device_id} 失败: {result.get('error')}")
        
        return jsonify({
            "success": True,
            "session_id": session.session_id,
            "message": "语音呼叫已发起，请浏览器端连接 WebSocket",
            "device_notified": device_notified,
            "iotda_msg_id": iotda_msg_id,
        }), 200
    
    except Exception as e:
        logger.exception(f"initiate_call 异常: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@voice_bp.route("/call/terminate", methods=["POST"])
def terminate_call():
    """
    终止语音呼叫
    
    请求体:
    {
        "session_id": "VIGIDOOR_xxx_RPI"
    }
    """
    try:
        data = request.get_json(silent=True) or {}
        
        session_id = data.get("session_id")
        if not session_id:
            return jsonify({
                "success": False,
                "error": "session_id 是必填项"
            }), 400
        
        session = session_manager.get_session(session_id)
        if not session:
            return jsonify({
                "success": False,
                "error": f"会话 {session_id} 不存在"
            }), 404
        
        # 通知设备断开（可选）
        if session.device_sid:
            from app.services.websocket_handler import socketio
            if socketio:
                socketio.emit(
                    'call_terminated',
                    {'message': '服务器已终止通话'},
                    to=session.device_sid
                )
        
        # 关闭会话
        session_manager.close_session(session_id)
        
        return jsonify({
            "success": True,
            "message": f"会话 {session_id} 已终止"
        }), 200
    
    except Exception as e:
        logger.exception(f"terminate_call 异常: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@voice_bp.route("/call/status/<session_id>", methods=["GET"])
def get_call_status(session_id: str):
    """
    获取语音呼叫状态
    
    响应:
    {
        "success": true,
        "session_id": "xxx",
        "status": "connected",
        "browser_connected": true,
        "device_connected": true,
        "created_at": 1234567890.123,
        "connected_at": 1234567891.456
    }
    """
    try:
        session = session_manager.get_session(session_id)
        
        if not session:
            return jsonify({
                "success": False,
                "error": f"会话 {session_id} 不存在"
            }), 404
        
        return jsonify({
            "success": True,
            "session_id": session.session_id,
            "device_id": session.device_id,
            "status": session.status.value,
            "browser_connected": session.browser_sid is not None,
            "device_connected": session.device_sid is not None,
            "created_at": session.created_at,
            "connected_at": session.connected_at,
            "browser_messages": session.browser_messages,
            "device_messages": session.device_messages,
        }), 200
    
    except Exception as e:
        logger.exception(f"get_call_status 异常: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@voice_bp.route("/sessions", methods=["GET"])
def list_sessions():
    """
    列出所有活跃会话（调试用）
    """
    try:
        sessions_info = session_manager.get_all_sessions_info()
        
        return jsonify({
            "success": True,
            "total": len(sessions_info),
            "sessions": sessions_info
        }), 200
    
    except Exception as e:
        logger.exception(f"list_sessions 异常: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
