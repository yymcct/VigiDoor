"""
ZLMediaKit Webhook 处理器
实现按需推流控制逻辑:
  - on_stream_not_found  → 有观看者请求流但流不存在 → 向设备下发推流开始指令
  - on_stream_none_reader → 流已存在但无任何观看者  → 向设备下发推流停止指令

ZLM 配置 (zlmediakit.ini):
    on_stream_not_found=http://<本服务地址>/vigidoor/index/hook/on_stream_not_found
    on_stream_none_reader=http://<本服务地址>/vigidoor/index/hook/on_stream_none_reader

约定:
  ZLM 的 stream 字段即为目标设备的 device_id
  例: stream="VIGIDOOR_7c3a41081017190d_RPI" → device_id="VIGIDOOR_7c3a41081017190d_RPI"
"""
import logging
from flask import Blueprint, request, jsonify
from app.services.iotda import send_device_command
from app.config import Config

logger = logging.getLogger(__name__)

zlm_bp = Blueprint("zlm_webhook", __name__)


def _build_rtmp_url(app_name: str, stream_name: str) -> str:
    """
    根据 ZLM 上报的 app / stream 构造设备推流目标 RTMP 地址

    格式: rtmp://<ZLM_SERVER>:<ZLM_RTMP_PORT>/<app>/<stream>
    """
    return f"rtmp://{Config.ZLM_SERVER}:{Config.ZLM_RTMP_PORT}/{app_name}/{stream_name}"


# ---------------------------------------------------------------------------
# on_stream_not_found
# ---------------------------------------------------------------------------

@zlm_bp.route("/on_stream_not_found", methods=["POST"])
def on_stream_not_found():
    """
    ZLMediaKit Webhook: 流不存在

    触发时机: 有客户端请求拉流，但 ZLM 上找不到对应的流
    本服务动作: 向对应的树莓派设备下发推流开始指令

    ZLM 请求体示例:
    {
        "mediaServerId": "your_server_id",
        "app":    "live",
        "stream": "VIGIDOOR_7c3a41081017190d_RPI",
        "schema": "rtsp",
        "ip":     "10.0.17.132",
        "port":   49614,
        "params": "",
        "vhost":  "__defaultVhost__",
        "id":     "140183261486112"
    }

    ZLM 期望响应:
    { "code": 0, "msg": "success" }
    """
    data = request.get_json(force=True, silent=True) or {}

    app_name        = data.get("app", "live")
    stream_name     = data.get("stream", "")
    schema          = data.get("schema", "")
    media_server_id = data.get("mediaServerId", "")

    logger.info(
        "[ZLM] on_stream_not_found | mediaServerId=%s app=%s stream=%s schema=%s",
        media_server_id, app_name, stream_name, schema,
    )

    if not stream_name:
        logger.warning("[ZLM] on_stream_not_found: stream 字段为空，跳过")
        return jsonify({"code": 0, "msg": "success"}), 200

    # stream 名称即设备 ID
    device_id = stream_name
    rtmp_url  = _build_rtmp_url(app_name, stream_name)

    # 构造推流开始命令
    command_data = {
        "action": "start",
        "rtmp_url": rtmp_url,
        "params": {
            "app":    app_name,
            "stream": stream_name,
            "schema": schema,
        },
    }

    result = send_device_command(device_id=device_id, message_data=command_data)

    if result["success"]:
        logger.info(
            "[ZLM] on_stream_not_found: 推流开始指令已下发 device_id=%s rtmp_url=%s",
            device_id, rtmp_url,
        )
    else:
        logger.error(
            "[ZLM] on_stream_not_found: 推流开始指令下发失败 device_id=%s error=%s",
            device_id, result.get("error"),
        )

    # 不论命令是否成功，均向 ZLM 返回 200 成功，避免 ZLM 报错
    return jsonify({"code": 0, "msg": "success"}), 200


# ---------------------------------------------------------------------------
# on_stream_none_reader
# ---------------------------------------------------------------------------

@zlm_bp.route("/on_stream_none_reader", methods=["POST"])
def on_stream_none_reader():
    """
    ZLMediaKit Webhook: 流无人观看

    触发时机: 某路流存在推流但已无任何拉流客户端
    本服务动作: 向对应的树莓派设备下发推流停止指令，并告知 ZLM 关闭该流

    ZLM 请求体示例:
    {
        "mediaServerId": "your_server_id",
        "app":    "live",
        "stream": "VIGIDOOR_7c3a41081017190d_RPI",
        "schema": "rtmp",
        "vhost":  "__defaultVhost__"
    }

    ZLM 期望响应:
    { "close": true, "code": 0 }
      close=true  → 通知 ZLM 主动关闭该路流
      close=false → 保留该路流（不停流）
    """
    data = request.get_json(force=True, silent=True) or {}

    app_name        = data.get("app", "live")
    stream_name     = data.get("stream", "")
    schema          = data.get("schema", "")
    media_server_id = data.get("mediaServerId", "")

    logger.info(
        "[ZLM] on_stream_none_reader | mediaServerId=%s app=%s stream=%s schema=%s",
        media_server_id, app_name, stream_name, schema,
    )

    if not stream_name:
        logger.warning("[ZLM] on_stream_none_reader: stream 字段为空，跳过")
        return jsonify({"close": True, "code": 0}), 200

    # stream 名称即设备 ID
    device_id = stream_name

    # 构造推流停止命令
    command_data = {
        "action": "stop",
        "params": {
            "app":    app_name,
            "stream": stream_name,
            "schema": schema,
        },
    }

    result = send_device_command(device_id=device_id, message_data=command_data)

    if result["success"]:
        logger.info(
            "[ZLM] on_stream_none_reader: 推流停止指令已下发 device_id=%s",
            device_id,
        )
    else:
        logger.error(
            "[ZLM] on_stream_none_reader: 推流停止指令下发失败 device_id=%s error=%s",
            device_id, result.get("error"),
        )

    # close=True 通知 ZLM 关闭该路流
    return jsonify({"close": True, "code": 0}), 200
