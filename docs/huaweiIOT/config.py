"""
配置文件
可根据需要修改默认配置
"""

import os

class Config:
    """基础配置"""
    
    # 华为云 IAM 认证配置
    IAM_USERNAME = os.getenv("HUAWEI_USERNAME", "iot")
    IAM_PASSWORD = os.getenv("HUAWEI_PASSWORD", "r&w5#GJ")
    IAM_DOMAIN_NAME = os.getenv("HUAWEI_DOMAIN", "henandahuaanfang")
    IAM_PROJECT_NAME = os.getenv("HUAWEI_PROJECT", "cn-north-4")
    IAM_REGION = os.getenv("HUAWEI_REGION", "cn-north-4")
    
    # IoTDA 服务配置
    IOTDA_ENDPOINT = os.getenv("IOTDA_ENDPOINT", f"https://iotda.{IAM_REGION}.myhuaweicloud.com")
    IOTDA_INSTANCE_ID = os.getenv("IOTDA_INSTANCE_ID", None)
    
    # 推流配置
    DEFAULT_RTMP_URL_TEMPLATE = os.getenv("RTMP_URL_TEMPLATE", "rtmp://zlm-server:1935/live/{device_id}")
    
    # 服务配置
    PORT = int(os.getenv("PORT", 5000))
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"


class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True


class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False


# 配置字典
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
