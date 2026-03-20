"""
IoTDA 服务层
封装华为云 IoTDA SDK，提供设备消息下发能力
"""
import json
import uuid
import time
import logging
from typing import Optional, Dict, Any

from huaweicloudsdkcore.auth.credentials import BasicCredentials, DerivedCredentials
from huaweicloudsdkcore.region.region import Region as CoreRegion
from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkiotda.v5 import (
    IoTDAClient,
    CreateMessageRequest,
    DeviceMessageRequest,
)

logger = logging.getLogger(__name__)

# IoTDA 客户端单例
_iotda_client: Optional[IoTDAClient] = None


def get_iotda_client() -> Optional[IoTDAClient]:
    """
    获取 IoTDA 客户端实例（单例模式）
    使用 AK/SK 认证方式
    """
    global _iotda_client

    if _iotda_client is not None:
        return _iotda_client

    # 延迟导入 Config，避免循环依赖
    from app.config import Config

    if not Config.HUAWEI_AK or not Config.HUAWEI_SK:
        logger.error("CLOUD_SDK_AK 和 CLOUD_SDK_SK 未配置")
        return None

    if not Config.HUAWEI_PROJECT_ID:
        logger.error("HUAWEI_PROJECT_ID 未配置")
        return None

    try:
        credentials = (
            BasicCredentials(Config.HUAWEI_AK, Config.HUAWEI_SK, Config.HUAWEI_PROJECT_ID)
            .with_derived_predicate(DerivedCredentials.get_default_derived_predicate())
        )

        _iotda_client = (
            IoTDAClient.new_builder()
            .with_credentials(credentials)
            .with_region(CoreRegion(id=Config.HUAWEI_REGION, endpoint=Config.IOTDA_ENDPOINT))
            .build()
        )

        logger.info("IoTDA 客户端初始化成功")
        return _iotda_client

    except Exception as e:
        logger.error(f"IoTDA 客户端初始化失败: {e}")
        return None


def send_device_command(device_id: str, message_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    通过华为云 IoTDA 向设备发送自定义 Topic 消息

    消息下发 Topic: vigidoor/down/{device_id}/command/stream

    消息体格式:
    {
        "msg_id": "<uuid>",
        "timestamp": 1770905346017,
        "device_id": "VIGIDOOR_xxx_RPI",
        "version": "1.0",
        "data": { ... }   # message_data 的内容
    }

    参考: https://support.huaweicloud.com/api-iothub/iot_06_v5_0059.html
    """
    client = get_iotda_client()
    if not client:
        return {"success": False, "error": "IoTDA 客户端未初始化"}

    msg_id = str(uuid.uuid4())
    timestamp = int(time.time() * 1000)

    full_message = {
        "msg_id": msg_id,
        "timestamp": timestamp,
        "device_id": device_id,
        "version": "1.0",
        "data": message_data,
    }

    topic_full_name = f"vigidoor/down/{device_id}/command/stream"

    try:
        logger.info(f"下发命令到设备: {device_id}")
        logger.debug(f"Topic: {topic_full_name}")
        logger.debug(f"Message: {json.dumps(full_message, ensure_ascii=False, indent=2)}")

        req = CreateMessageRequest()
        req.device_id = device_id
        req.body = DeviceMessageRequest(
            topic_full_name=topic_full_name,
            message=json.dumps(full_message, ensure_ascii=False),
            name="StreamControl",
            message_id=msg_id,
        )

        response = client.create_message(req)

        logger.info(f"命令下发成功: message_id={msg_id}")
        return {
            "success": True,
            "msg_id": msg_id,
            "timestamp": timestamp,
            "response": {
                "message_id": getattr(response, "message_id", msg_id),
                "status": getattr(response, "status", "sent"),
            },
        }

    except exceptions.ClientRequestException as e:
        error_msg = f"IoTDA API 错误: {e.status_code}"
        logger.error(f"{error_msg} - {e.error_code}: {e.error_msg}")
        return {
            "success": False,
            "error": error_msg,
            "error_code": e.error_code,
            "error_msg": e.error_msg,
            "request_id": e.request_id,
        }

    except Exception as e:
        error_msg = f"命令下发异常: {e}"
        logger.exception(error_msg)
        return {"success": False, "error": error_msg}


def send_audio_command(
    device_id: str,
    action: str,
    params: Optional[Dict[str, Any]] = None,
    namespace: str = "vigidoor",
) -> Dict[str, Any]:
    """
    通过华为云 IoTDA 下发远程喊话音频控制命令。

    Topic:
        {namespace}/down/{device_id}/command/audio

    消息体格式:
    {
        "device_id": "device123",
        "version": "1.0",
        "msg_id": "uuid",
        "timestamp": 1719999999999,
        "data": {
            "action": "initiate_call | terminate_call",
            "params": {...}
        }
    }
    """
    client = get_iotda_client()
    if not client:
        return {"success": False, "error": "IoTDA 客户端未初始化"}

    msg_id = str(uuid.uuid4())
    timestamp = int(time.time() * 1000)
    topic_full_name = f"{namespace}/down/{device_id}/command/audio"

    full_message = {
        "device_id": device_id,
        "version": "1.0",
        "msg_id": msg_id,
        "timestamp": timestamp,
        "data": {
            "action": action,
            "params": params or {},
        },
    }

    try:
        logger.info(f"下发音频命令到设备: {device_id}, action={action}")
        logger.debug(f"Topic: {topic_full_name}")
        logger.debug(f"Message: {json.dumps(full_message, ensure_ascii=False, indent=2)}")

        req = CreateMessageRequest()
        req.device_id = device_id
        req.body = DeviceMessageRequest(
            topic_full_name=topic_full_name,
            message=json.dumps(full_message, ensure_ascii=False),
            name="AudioControl",
            message_id=msg_id,
        )

        response = client.create_message(req)

        logger.info(f"音频命令下发成功: message_id={msg_id}, action={action}")
        return {
            "success": True,
            "msg_id": msg_id,
            "timestamp": timestamp,
            "topic": topic_full_name,
            "action": action,
            "response": {
                "message_id": getattr(response, "message_id", msg_id),
                "status": getattr(response, "status", "sent"),
            },
        }

    except exceptions.ClientRequestException as e:
        error_msg = f"IoTDA API 错误: {e.status_code}"
        logger.error(f"{error_msg} - {e.error_code}: {e.error_msg}")
        return {
            "success": False,
            "error": error_msg,
            "error_code": e.error_code,
            "error_msg": e.error_msg,
            "request_id": e.request_id,
        }

    except Exception as e:
        error_msg = f"音频命令下发异常: {e}"
        logger.exception(error_msg)
        return {"success": False, "error": error_msg}


def start_remote_talk(device_id: str, ws_url: str, namespace: str = "vigidoor") -> Dict[str, Any]:
    """
    开始远程喊话。

    data.action 固定为 initiate_call，params.url 为设备需连接的 WebSocket 地址。
    """
    if not ws_url:
        return {"success": False, "error": "ws_url 不能为空"}

    return send_audio_command(
        device_id=device_id,
        action="initiate_call",
        params={"websocket_url": ws_url},
        namespace=namespace,
    )


def stop_remote_talk(device_id: str, namespace: str = "vigidoor") -> Dict[str, Any]:
    """
    结束远程喊话。

    data.action 固定为 terminate_call，params 为空对象。
    """
    return send_audio_command(
        device_id=device_id,
        action="terminate_call",
        params={},
        namespace=namespace,
    )


def send_security_command(
    device_id: str,
    action: str,
    namespace: str = "vigidoor",
) -> Dict[str, Any]:
    """
    通过华为云 IoTDA 下发布防/撤防指令。

    Topic:
        {namespace}/down/{device_id}/command/security

    消息体格式:
    {
        "device_id": "VIGIDOOR_xxx",
        "msg_id": "<uuid>",
        "timestamp": 1770905346017,
        "version": "1.0",
        "data": {
            "action": "arm"  // 或 "disarm"
        }
    }

    参数:
        device_id: 设备 ID
        action:    "arm"（布防）或 "disarm"（撤防）
        namespace: Topic 命名空间，默认 "vigidoor"
    """
    if action not in ("arm", "disarm"):
        return {"success": False, "error": f"无效的 action: {action}，应为 'arm' 或 'disarm'"}

    client = get_iotda_client()
    if not client:
        return {"success": False, "error": "IoTDA 客户端未初始化"}

    msg_id = str(uuid.uuid4())
    timestamp = int(time.time() * 1000)
    topic_full_name = f"{namespace}/down/{device_id}/command/security"

    full_message = {
        "device_id": device_id,
        "msg_id": msg_id,
        "timestamp": timestamp,
        "version": "1.0",
        "data": {
            "action": action,
        },
    }

    try:
        action_label = "布防" if action == "arm" else "撤防"
        logger.info(f"下发{action_label}指令到设备: {device_id}")
        logger.debug(f"Topic: {topic_full_name}")
        logger.debug(f"Message: {json.dumps(full_message, ensure_ascii=False, indent=2)}")

        req = CreateMessageRequest()
        req.device_id = device_id
        req.body = DeviceMessageRequest(
            topic_full_name=topic_full_name,
            message=json.dumps(full_message, ensure_ascii=False),
            name="SecurityControl",
            message_id=msg_id,
        )

        response = client.create_message(req)

        logger.info(f"{action_label}指令下发成功: message_id={msg_id}")
        return {
            "success": True,
            "msg_id": msg_id,
            "timestamp": timestamp,
            "topic": topic_full_name,
            "action": action,
            "response": {
                "message_id": getattr(response, "message_id", msg_id),
                "status": getattr(response, "status", "sent"),
            },
        }

    except exceptions.ClientRequestException as e:
        error_msg = f"IoTDA API 错误: {e.status_code}"
        logger.error(f"{error_msg} - {e.error_code}: {e.error_msg}")
        return {
            "success": False,
            "error": error_msg,
            "error_code": e.error_code,
            "error_msg": e.error_msg,
            "request_id": e.request_id,
        }

    except Exception as e:
        error_msg = f"安防指令下发异常: {e}"
        logger.exception(error_msg)
        return {"success": False, "error": error_msg}
