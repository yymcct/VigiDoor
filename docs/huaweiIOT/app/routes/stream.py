"""
推流控制路由
提供手动触发推流开始 / 停止的 REST API
"""
import logging
from flask import Blueprint, request, jsonify
from app.services.iotda import send_device_command, get_iotda_client
from app.config import Config

logger = logging.getLogger(__name__)

stream_bp = Blueprint("stream", __name__)


@stream_bp.route("/stream/start", methods=["POST"])
def start_stream():
    """
    主动开始推流

    请求体:
    {
        "device_id": "VIGIDOOR_xxx_RPI",
        "rtmp_url":  "rtmp://zlm-server:1935/live/VIGIDOOR_xxx_RPI",  // 可选
        "params":    {}                                                // 可选
    }
    """
    try:
        data = request.get_json(silent=True) or {}

        device_id = data.get("device_id")
        if not device_id:
            return jsonify({"success": False, "error": "device_id 为必填项"}), 400

        rtmp_url = data.get("rtmp_url") or Config.DEFAULT_RTMP_URL_TEMPLATE.format(
            device_id=device_id
        )
        params = data.get("params", {})

        command_data = {
            "action": "start",
            "rtmp_url": rtmp_url,
            "params": params,
        }

        result = send_device_command(device_id=device_id, message_data=command_data)

        if result["success"]:
            return jsonify({
                "success": True,
                "message": f"推流开始指令已下发至设备 {device_id}",
                "device_id": device_id,
                "rtmp_url": rtmp_url,
                "msg_id": result.get("msg_id"),
            }), 200
        else:
            return jsonify(result), 500

    except Exception as e:
        logger.exception(f"start_stream 异常: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@stream_bp.route("/stream/stop", methods=["POST"])
def stop_stream():
    """
    主动停止推流

    请求体:
    {
        "device_id": "VIGIDOOR_xxx_RPI"
    }
    """
    try:
        data = request.get_json(silent=True) or {}

        device_id = data.get("device_id")
        if not device_id:
            return jsonify({"success": False, "error": "device_id 为必填项"}), 400

        command_data = {"action": "stop"}

        result = send_device_command(device_id=device_id, message_data=command_data)

        if result["success"]:
            return jsonify({
                "success": True,
                "message": f"推流停止指令已下发至设备 {device_id}",
                "device_id": device_id,
                "msg_id": result.get("msg_id"),
            }), 200
        else:
            return jsonify(result), 500

    except Exception as e:
        logger.exception(f"stop_stream 异常: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@stream_bp.route("/config/check", methods=["GET"])
def check_config():
    """检查 IoTDA 配置是否可用"""
    client = get_iotda_client()
    if client:
        return jsonify({
            "success": True,
            "message": "配置有效，IoTDA 客户端初始化成功",
            "config": {
                "region": Config.HUAWEI_REGION,
                "endpoint": Config.IOTDA_ENDPOINT,
                "project_id": Config.HUAWEI_PROJECT_ID,
                "ak_configured": bool(Config.HUAWEI_AK),
                "sk_configured": bool(Config.HUAWEI_SK),
            },
        }), 200
    else:
        return jsonify({
            "success": False,
            "error": "IoTDA 客户端初始化失败，请检查配置",
        }), 500
