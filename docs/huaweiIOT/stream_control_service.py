#!/usr/bin/env python3
"""
华为云 IoT 推流控制服务
提供 Flask API 接口，通过华为云 IoTDA 服务向设备发送推流控制命令
使用华为云官方 SDK
"""

import os
import json
import uuid
import time
from flask import Flask, request, jsonify
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# 华为云 SDK
from huaweicloudsdkcore.auth.credentials import BasicCredentials, DerivedCredentials
from huaweicloudsdkcore.region.region import Region as CoreRegion
from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkiotda.v5 import *

# 加载 .env 文件
load_dotenv()

app = Flask(__name__)

# ==================== 配置区 ====================
# 华为云认证配置 (使用 AK/SK 方式，更安全)
HUAWEI_AK = os.getenv("CLOUD_SDK_AK", "")
HUAWEI_SK = os.getenv("CLOUD_SDK_SK", "")
HUAWEI_PROJECT_ID = os.getenv("HUAWEI_PROJECT_ID", "")
HUAWEI_REGION = os.getenv("HUAWEI_REGION", "cn-north-4")

# IoTDA 服务配置
# ENDPOINT 格式: https://xxxxxx.iotda.cn-north-4.myhuaweicloud.com (应用侧 HTTPS 地址)
IOTDA_ENDPOINT = os.getenv("IOTDA_ENDPOINT", f"https://bf0f7e134a.st1.iotda-app.cn-north-4.myhuaweicloud.com")

# 推流配置
DEFAULT_RTMP_URL_TEMPLATE = os.getenv("RTMP_URL_TEMPLATE", "rtmp://zlm-server:1935/live/{device_id}")

# IoTDA 客户端实例
_iotda_client: Optional[IoTDAClient] = None

# ==================== IoTDA 客户端初始化 ====================

def get_iotda_client() -> Optional[IoTDAClient]:
    """
    获取 IoTDA 客户端实例（单例模式）
    使用 AK/SK 认证方式
    """
    global _iotda_client
    
    if _iotda_client is not None:
        return _iotda_client
    
    # 参数校验
    if not HUAWEI_AK or not HUAWEI_SK:
        app.logger.error("CLOUD_SDK_AK and CLOUD_SDK_SK must be set in environment variables")
        return None
    
    if not HUAWEI_PROJECT_ID:
        app.logger.error("HUAWEI_PROJECT_ID must be set in environment variables")
        return None
    
    try:
        # 创建认证凭据
        credentials = BasicCredentials(HUAWEI_AK, HUAWEI_SK, HUAWEI_PROJECT_ID) \
            .with_derived_predicate(DerivedCredentials.get_default_derived_predicate())
        
        # 创建客户端
        _iotda_client = IoTDAClient.new_builder() \
            .with_credentials(credentials) \
            .with_region(CoreRegion(id=HUAWEI_REGION, endpoint=IOTDA_ENDPOINT)) \
            .build()
        
        app.logger.info("IoTDA client initialized successfully")
        return _iotda_client
        
    except Exception as e:
        app.logger.error(f"Failed to initialize IoTDA client: {str(e)}")
        return None


# ==================== IoTDA 命令下发 ====================

def send_device_command(device_id: str, message_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    通过华为云 IoTDA SDK 向设备发送命令
    使用自定义 Topic 消息下发
    
    参考: https://support.huaweicloud.com/api-iothub/iot_06_v5_0059.html
    """
    client = get_iotda_client()
    if not client:
        return {
            "success": False,
            "error": "IoTDA client not initialized"
        }
    
    # 构建完整的消息负载
    msg_id = str(uuid.uuid4())
    timestamp = int(time.time() * 1000)
    
    # 完整的消息体
    full_message = {
        "msg_id": msg_id,
        "timestamp": timestamp,
        "device_id": device_id,
        "version": "1.0",
        "data": message_data
    }
    
    # 自定义 Topic (需要在平台上预先配置) f"$oc/devices/{device_id}/user/stream/control"
    topic_full_name = f"vigidoor/down/{device_id}/command/stream"
   
    """
    {
        "msg_id": "f61577db-659b-4179-b187-ce7cd7c8e2cb",
        "timestamp": 1770905346017,
        "device_id": "VIGIDOOR_7c3a41081017190d_RPI",
        "version": "1.0",
        "data": {
            "action": "stop"
        }
    }
    """
    try:
        app.logger.info(f"Sending command to device {device_id}")
        app.logger.debug(f"Topic: {topic_full_name}")
        app.logger.debug(f"Message: {json.dumps(full_message, indent=2)}")
        
        # 创建消息下发请求
        request = CreateMessageRequest()
        request.device_id = device_id
        request.body = DeviceMessageRequest(
            topic_full_name=topic_full_name,
            message=json.dumps(full_message),
            name="StreamControl",
            message_id=msg_id
        )
        
        # 发送消息
        response = client.create_message(request)
        
        app.logger.info(f"Command sent successfully: message_id={msg_id}")
        return {
            "success": True,
            "msg_id": msg_id,
            "timestamp": timestamp,
            "response": {
                "message_id": response.message_id if hasattr(response, 'message_id') else msg_id,
                "status": response.status if hasattr(response, 'status') else "sent"
            }
        }
        
    except exceptions.ClientRequestException as e:
        error_msg = f"IoTDA API error: {e.status_code}"
        app.logger.error(f"{error_msg} - {e.error_code}: {e.error_msg}")
        return {
            "success": False,
            "error": error_msg,
            "error_code": e.error_code,
            "error_msg": e.error_msg,
            "request_id": e.request_id
        }
        
    except Exception as e:
        error_msg = f"Exception when sending command: {str(e)}"
        app.logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg
        }


# ==================== Flask 路由 ====================

@app.route('/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify({
        "status": "healthy",
        "service": "stream-control-service",
        "timestamp": int(time.time() * 1000)
    })


@app.route('/api/v1/stream/start', methods=['POST'])
def start_stream():
    """
    开始推流接口
    
    请求体:
    {
        "device_id": "RPI_001",
        "rtmp_url": "rtmp://zlm-server:1935/live/RPI_001",  // 可选，不传则使用默认模板
        "params": {}  // 可选，额外参数
    }
    """
    try:
        data = request.get_json()
        
        # 参数校验
        if not data:
            return jsonify({
                "success": False,
                "error": "Request body is required"
            }), 400
        
        device_id = data.get("device_id")
        if not device_id:
            return jsonify({
                "success": False,
                "error": "device_id is required"
            }), 400
        
        # 获取或生成 RTMP URL
        rtmp_url = data.get("rtmp_url")
        if not rtmp_url:
            rtmp_url = DEFAULT_RTMP_URL_TEMPLATE.format(device_id=device_id)
        
        params = data.get("params", {})
        
        # 构建推流开始命令
        command_data = {
            "action": "start",
            "rtmp_url": rtmp_url,
            "params": params
        }
        
        # 发送命令
        result = send_device_command(
            device_id=device_id,
            message_data=command_data
        )
        
        if result["success"]:
            return jsonify({
                "success": True,
                "message": f"Stream start command sent to device {device_id}",
                "device_id": device_id,
                "rtmp_url": rtmp_url,
                "msg_id": result.get("msg_id")
            }), 200
        else:
            return jsonify(result), 500
            
    except Exception as e:
        app.logger.error(f"Error in start_stream: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/v1/stream/stop', methods=['POST'])
def stop_stream():
    """
    停止推流接口
    
    请求体:
    {
        "device_id": "RPI_001"
    }
    """
    try:
        data = request.get_json()
        
        # 参数校验
        if not data:
            return jsonify({
                "success": False,
                "error": "Request body is required"
            }), 400
        
        device_id = data.get("device_id")
        if not device_id:
            return jsonify({
                "success": False,
                "error": "device_id is required"
            }), 400
        
        # 构建推流停止命令
        command_data = {
            "action": "stop"
        }
        
        # 发送命令
        result = send_device_command(
            device_id=device_id,
            message_data=command_data
        )
        
        if result["success"]:
            return jsonify({
                "success": True,
                "message": f"Stream stop command sent to device {device_id}",
                "device_id": device_id,
                "msg_id": result.get("msg_id")
            }), 200
        else:
            return jsonify(result), 500
            
    except Exception as e:
        app.logger.error(f"Error in stop_stream: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/v1/config/check', methods=['GET'])
def check_config():
    """检查配置是否正确"""
    client = get_iotda_client()
    if client:
        return jsonify({
            "success": True,
            "message": "Configuration is valid, IoTDA client initialized",
            "config": {
                "region": HUAWEI_REGION,
                "endpoint": IOTDA_ENDPOINT,
                "project_id": HUAWEI_PROJECT_ID,
                "ak_configured": bool(HUAWEI_AK),
                "sk_configured": bool(HUAWEI_SK)
            }
        }), 200
    else:
        return jsonify({
            "success": False,
            "error": "Failed to initialize IoTDA client, please check configuration"
        }), 500


# ==================== 主入口 ====================

if __name__ == '__main__':
    # 配置日志
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 启动时初始化客户端以验证配置
    app.logger.info("Initializing service...")
    app.logger.info(f"IoTDA Endpoint: {IOTDA_ENDPOINT}")
    app.logger.info(f"Region: {HUAWEI_REGION}")
    app.logger.info(f"Project ID: {HUAWEI_PROJECT_ID}")
    
    client = get_iotda_client()
    if client:
        app.logger.info("IoTDA client initialized successfully, service ready")
    else:
        app.logger.error("Failed to initialize IoTDA client")
        app.logger.error("Please check environment variables: CLOUD_SDK_AK, CLOUD_SDK_SK, HUAWEI_PROJECT_ID")
    
    # 启动 Flask 服务
    port = int(os.getenv("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
