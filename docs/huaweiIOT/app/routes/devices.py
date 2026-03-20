"""
设备管理路由
提供查询华为云 IoTDA 设备列表的 REST API
"""
import logging
from flask import Blueprint, request, jsonify
from app.services.iotda import list_devices

logger = logging.getLogger(__name__)

devices_bp = Blueprint("devices", __name__)


@devices_bp.route("/devices", methods=["GET"])
def get_devices():
    """
    查询设备列表

    查询参数 (均可选):
        product_id  - 按产品 ID 过滤
        device_name - 按设备名称模糊匹配
        limit       - 每页条数，默认 50
        marker      - 分页游标

    响应示例:
    {
        "success": true,
        "count": 4,
        "devices": [
            {
                "device_id": "VIGIDOOR_xxx_RPI",
                "device_name": "PI5-2",
                "status": "ONLINE",
                ...
            }
        ],
        "marker": null
    }
    """
    product_id = request.args.get("product_id")
    device_name = request.args.get("device_name")
    marker = request.args.get("marker")

    try:
        limit = int(request.args.get("limit", 50))
        if limit < 1 or limit > 50:
            limit = 50
    except (ValueError, TypeError):
        limit = 50

    result = list_devices(
        product_id=product_id,
        device_name=device_name,
        limit=limit,
        marker=marker,
    )

    if result.get("success"):
        return jsonify(result), 200
    else:
        return jsonify(result), 500
