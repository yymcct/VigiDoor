"""
安防控制路由
提供布防/撤防 REST API，通过 MQTT 下发指令至设备
"""
import logging
from flask import Blueprint, request, jsonify
from app.services.iotda import send_security_command

logger = logging.getLogger(__name__)

security_bp = Blueprint("security", __name__)


@security_bp.route("/security/arm", methods=["POST"])
def arm():
    """
    布防

    请求体:
    {
        "device_id": "VIGIDOOR_xxx"
    }

    响应:
    {
        "success": true,
        "message": "布防指令已下发至设备 VIGIDOOR_xxx",
        "device_id": "VIGIDOOR_xxx",
        "msg_id": "<uuid>"
    }
    """
    return _handle_security_action("arm")


@security_bp.route("/security/disarm", methods=["POST"])
def disarm():
    """
    撤防

    请求体:
    {
        "device_id": "VIGIDOOR_xxx"
    }

    响应:
    {
        "success": true,
        "message": "撤防指令已下发至设备 VIGIDOOR_xxx",
        "device_id": "VIGIDOOR_xxx",
        "msg_id": "<uuid>"
    }
    """
    return _handle_security_action("disarm")


def _handle_security_action(action: str):
    """公共处理逻辑：验证参数，调用服务层，返回统一响应。"""
    try:
        data = request.get_json(silent=True) or {}

        device_id = data.get("device_id")
        if not device_id:
            return jsonify({"success": False, "error": "device_id 为必填项"}), 400

        result = send_security_command(device_id=device_id, action=action)

        action_label = "布防" if action == "arm" else "撤防"
        if result["success"]:
            return jsonify({
                "success": True,
                "message": f"{action_label}指令已下发至设备 {device_id}",
                "device_id": device_id,
                "msg_id": result.get("msg_id"),
                "topic": result.get("topic"),
            }), 200
        else:
            return jsonify(result), 500

    except Exception as e:
        logger.exception(f"security/{action} 异常: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
