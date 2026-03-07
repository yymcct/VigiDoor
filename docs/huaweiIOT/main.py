#!/usr/bin/env python3
"""
入口文件
启动 Flask 推流控制服务
"""
import logging
import os
from logging.handlers import RotatingFileHandler
from app import create_app
from app.config import Config
from app.services.iotda import get_iotda_client


def _setup_logging() -> None:
    """配置全局日志：同时输出到控制台和本地滚动文件"""
    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # 控制台 Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(fmt)
    root.addHandler(console_handler)

    # 文件 Handler（滚动日志）
    if Config.LOG_FILE:
        log_dir = os.path.dirname(Config.LOG_FILE)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        file_handler = RotatingFileHandler(
            Config.LOG_FILE,
            maxBytes=Config.LOG_MAX_BYTES,
            backupCount=Config.LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setFormatter(fmt)
        root.addHandler(file_handler)


# ==================== 日志配置 ====================
_setup_logging()
logger = logging.getLogger(__name__)

# ==================== 创建应用 ====================
app = create_app()

# ==================== 主入口 ====================
if __name__ == "__main__":
    logger.info("=== 推流控制服务启动 ===")
    logger.info(f"IoTDA Endpoint : {Config.IOTDA_ENDPOINT}")
    logger.info(f"Region         : {Config.HUAWEI_REGION}")
    logger.info(f"Project ID     : {Config.HUAWEI_PROJECT_ID}")
    logger.info(f"ZLM Server     : {Config.ZLM_SERVER}:{Config.ZLM_RTMP_PORT}")
    logger.info(f"Listen Port    : {Config.PORT}")
    logger.info(f"WebSocket      : 已启用（Socket.IO）")

    # 预初始化 IoTDA 客户端，验证配置
    client = get_iotda_client()
    if client:
        logger.info("IoTDA 客户端初始化成功，服务就绪")
    else:
        logger.warning(
            "IoTDA 客户端初始化失败，请检查环境变量: "
            "CLOUD_SDK_AK / CLOUD_SDK_SK / HUAWEI_PROJECT_ID / IOTDA_ENDPOINT"
        )

    # 使用 SocketIO 运行应用（而不是 app.run）
    socketio = app.socketio
    socketio.run(
        app,
        host="0.0.0.0",
        port=Config.PORT,
        debug=Config.DEBUG,
        use_reloader=Config.DEBUG,
        log_output=False,
    )
