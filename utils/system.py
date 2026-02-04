"""
系统检测工具
"""

import os
from .logger import setup_logger

logger = setup_logger('system_utils')


def is_raspberry_pi() -> bool:
    """
    检测当前系统是否为树莓派
    
    Returns:
        bool: 如果是树莓派返回 True，否则返回 False
    """
    try:
        # 方法1: 检查设备树模型文件
        if os.path.exists('/proc/device-tree/model'):
            with open('/proc/device-tree/model', 'r') as f:
                model = f.read().lower()
                if 'raspberry pi' in model:
                    logger.debug("通过设备树模型检测到树莓派系统")
                    return True
        
        # 方法2: 检查 CPU 信息
        if os.path.exists('/proc/cpuinfo'):
            with open('/proc/cpuinfo', 'r') as f:
                cpuinfo = f.read().lower()
                if 'raspberry pi' in cpuinfo or 'bcm' in cpuinfo:
                    logger.debug("通过CPU信息检测到树莓派系统")
                    return True
        
        logger.debug("未检测到树莓派系统特征")
        return False
        
    except Exception as e:
        logger.warning(f"检测树莓派系统时出错: {e}，默认为非树莓派")
        return False
