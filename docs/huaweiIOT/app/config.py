#!/usr/bin/env python3
"""
全局配置模块
从环境变量加载所有配置项
"""
import os
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()


class Config:
    # ==================== 华为云认证 ====================
    HUAWEI_AK: str = os.getenv("CLOUD_SDK_AK", "")
    HUAWEI_SK: str = os.getenv("CLOUD_SDK_SK", "")
    HUAWEI_PROJECT_ID: str = os.getenv("HUAWEI_PROJECT_ID", "")
    HUAWEI_REGION: str = os.getenv("HUAWEI_REGION", "cn-north-4")

    # IoTDA 应用侧 HTTPS 地址
    # 格式: https://xxxxxx.iotda-app.cn-north-4.myhuaweicloud.com
    IOTDA_ENDPOINT: str = os.getenv(
        "IOTDA_ENDPOINT",
        "https://bf0f7e134a.st1.iotda-app.cn-north-4.myhuaweicloud.com"
    )

    # ==================== ZLMediaKit ====================
    # ZLM 服务主机名（容器名或 IP，用于构造设备推流目标地址）
    ZLM_SERVER: str = os.getenv("ZLM_SERVER", "zlm-server")
    ZLM_RTMP_PORT: int = int(os.getenv("ZLM_RTMP_PORT", "1935"))

    # 默认 RTMP 推流地址模板（外部调用 /api/v1/stream/start 时使用）
    DEFAULT_RTMP_URL_TEMPLATE: str = os.getenv(
        "RTMP_URL_TEMPLATE",
        "rtmp://zlm-server:1935/live/{device_id}"
    )

    # ==================== 服务 ====================
    PORT: int = int(os.getenv("PORT", "5002"))
    DEBUG: bool = os.getenv("FLASK_DEBUG", "false").lower() == "true"

    # ==================== WebSocket 语音中继 ====================
    # WebSocket 连接超时时间（秒）：等待双方建立连接的最大时间
    WS_CONNECTION_TIMEOUT: int = int(os.getenv("WS_CONNECTION_TIMEOUT", "30"))
    
    # WebSocket 会话超时时间（秒）：单方连接后等待另一方的最大时间
    WS_SESSION_TIMEOUT: int = int(os.getenv("WS_SESSION_TIMEOUT", "60"))
    
    # WebSocket 心跳间隔（秒）
    WS_HEARTBEAT_INTERVAL: int = int(os.getenv("WS_HEARTBEAT_INTERVAL", "30"))
    
    # 允许的最大并发语音会话数
    MAX_CONCURRENT_SESSIONS: int = int(os.getenv("MAX_CONCURRENT_SESSIONS", "100"))

    # WebSocket 服务地址（为空则自动根据请求生成）
    WS_URL: str = os.getenv("WS_URL", "")

    # ==================== 日志 ====================
    # 日志文件路径，留空则只输出到控制台
    LOG_FILE: str = os.getenv("LOG_FILE", "logs/app.log")
    LOG_MAX_BYTES: int = int(os.getenv("LOG_MAX_BYTES", str(10 * 1024 * 1024)))  # 10 MB
    LOG_BACKUP_COUNT: int = int(os.getenv("LOG_BACKUP_COUNT", "5"))
