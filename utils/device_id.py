"""
设备ID自动生成工具
基于硬件信息生成唯一的设备ID
"""

import os
import hashlib
import uuid
from typing import Optional

# 支持直接运行和作为模块导入
try:
    from .logger import setup_logger
    from .system import is_raspberry_pi
except ImportError:
    # 直接运行时的导入
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from utils.logger import setup_logger
    from utils.system import is_raspberry_pi

logger = setup_logger('device_id')


def get_mac_address() -> Optional[str]:
    """
    获取第一个非lo网卡的MAC地址
    
    Returns:
        MAC地址（如：a1:b2:c3:d4:e5:f6），如果获取失败返回None
    """
    try:
        # 尝试从 /sys/class/net 读取
        net_dir = '/sys/class/net'
        if os.path.exists(net_dir):
            for interface in os.listdir(net_dir):
                # 跳过回环接口
                if interface == 'lo':
                    continue
                
                mac_file = os.path.join(net_dir, interface, 'address')
                if os.path.exists(mac_file):
                    with open(mac_file, 'r') as f:
                        mac = f.read().strip()
                        if mac and mac != '00:00:00:00:00:00':
                            logger.debug(f"从 {interface} 获取到MAC地址: {mac}")
                            return mac
        
        # 备用方法：使用uuid模块
        mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff)
                       for elements in range(0, 2*6, 2)][::-1])
        if mac != '00:00:00:00:00:00':
            logger.debug(f"通过uuid.getnode()获取到MAC地址: {mac}")
            return mac
        
        logger.warning("无法获取有效的MAC地址")
        return None
        
    except Exception as e:
        logger.error(f"获取MAC地址时出错: {e}")
        return None


def get_cpu_serial() -> Optional[str]:
    """
    获取CPU序列号（仅树莓派可用）
    
    Returns:
        CPU序列号，如果获取失败返回None
    """
    try:
        if not is_raspberry_pi():
            return None
        
        # 树莓派的CPU序列号在 /proc/cpuinfo 中
        with open('/proc/cpuinfo', 'r') as f:
            for line in f:
                if line.startswith('Serial'):
                    serial = line.split(':')[1].strip()
                    logger.debug(f"获取到CPU序列号: {serial}")
                    return serial
        
        logger.warning("未能在 /proc/cpuinfo 中找到CPU序列号")
        return None
        
    except Exception as e:
        logger.error(f"获取CPU序列号时出错: {e}")
        return None


def get_machine_id() -> Optional[str]:
    """
    获取Linux机器ID（来自 /etc/machine-id 或 /var/lib/dbus/machine-id）
    
    Returns:
        机器ID，如果获取失败返回None
    """
    machine_id_paths = [
        '/etc/machine-id',
        '/var/lib/dbus/machine-id'
    ]
    
    for path in machine_id_paths:
        try:
            if os.path.exists(path):
                with open(path, 'r') as f:
                    machine_id = f.read().strip()
                    if machine_id:
                        logger.debug(f"从 {path} 获取到机器ID: {machine_id}")
                        return machine_id
        except Exception as e:
            logger.debug(f"从 {path} 读取机器ID失败: {e}")
            continue
    
    logger.warning("无法获取Linux机器ID")
    return None


def generate_device_id() -> str:
    """
    生成设备唯一ID
    
    生成规则：
    1. 优先使用硬件信息：CPU序列号（树莓派）或MAC地址
    2. 其次使用Linux机器ID
    3. 最后使用随机UUID（不推荐，每次启动会变化）
    
    格式：<prefix>_<hardware_hash>_<system_type>
    - prefix: 固定前缀，用于标识设备系列
    - hardware_hash: 硬件信息的MD5哈希值（前16位）
    - system_type: 系统类型标识（RPI=树莓派, UBT=Ubuntu/其他Linux）
    
    Returns:
        设备ID字符串（如：VIGIDOOR_abc123def4567890_RPI）
    """
    hardware_info = []
    system_type = "RPI" if is_raspberry_pi() else "UBT"
    
    # 1. 尝试获取CPU序列号（树莓派专有）
    cpu_serial = get_cpu_serial()
    if cpu_serial:
        hardware_info.append(f"cpu:{cpu_serial}")
        logger.info(f"使用CPU序列号生成设备ID（树莓派）")
    
    # 2. 获取MAC地址（所有系统通用）
    mac_address = get_mac_address()
    if mac_address:
        hardware_info.append(f"mac:{mac_address}")
        logger.info(f"使用MAC地址生成设备ID")
    
    # 3. 获取Linux机器ID（备用）
    machine_id = get_machine_id()
    if machine_id:
        hardware_info.append(f"machine:{machine_id}")
        logger.info(f"使用机器ID生成设备ID")
    
    # 4. 如果都获取失败，使用随机UUID（警告用户）
    if not hardware_info:
        fallback_uuid = str(uuid.uuid4())
        hardware_info.append(f"uuid:{fallback_uuid}")
        logger.warning(
            "无法获取任何硬件信息，使用随机UUID生成设备ID。"
            "注意：每次启动设备ID可能会变化！"
        )
    
    # 生成硬件信息的哈希值
    combined_info = '|'.join(hardware_info)
    hash_object = hashlib.md5(combined_info.encode())
    hardware_hash = hash_object.hexdigest()[:16]
    
    # 组装设备ID
    device_id = f"VIGIDOOR_{hardware_hash}_{system_type}"
    
    logger.info(f"生成的设备ID: {device_id}")
    logger.debug(f"硬件信息来源: {hardware_info}")
    
    return device_id


def get_device_id() -> str:
    """
    获取设备ID（包装函数，方便其他模块调用）
    
    Returns:
        设备ID字符串
    """
    return generate_device_id()


if __name__ == "__main__":
    # 测试代码
    print(f"系统类型: {'树莓派' if is_raspberry_pi() else 'Ubuntu/其他Linux'}")
    print(f"MAC地址: {get_mac_address()}")
    print(f"CPU序列号: {get_cpu_serial()}")
    print(f"机器ID: {get_machine_id()}")
    print(f"生成的设备ID: {generate_device_id()}")
