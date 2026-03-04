"""
健康检查路由
"""
import time
from flask import Blueprint, jsonify

health_bp = Blueprint("health", __name__)


@health_bp.route("/health", methods=["GET"])
def health_check():
    """健康检查接口"""
    return jsonify({
        "status": "healthy",
        "service": "stream-control-service",
        "timestamp": int(time.time() * 1000),
    })
