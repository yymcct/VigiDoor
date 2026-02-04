#!/usr/bin/env python3
"""
测试设备ID自动生成和配置管理器集成
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.config import ConfigManager
from utils.device_id import get_device_id

def test_device_id():
    """测试设备ID生成"""
    print("=" * 60)
    print("测试1: 直接生成设备ID")
    print("=" * 60)
    device_id = get_device_id()
    print(f"设备ID: {device_id}")
    print()

def test_config_manager():
    """测试配置管理器中的设备ID"""
    print("=" * 60)
    print("测试2: 配置管理器集成")
    print("=" * 60)
    
    # 初始化配置管理器
    config = ConfigManager.initialize('config.yaml')
    
    print(f"设备ID: {config.device.id}")
    print(f"设备名称: {config.device.name}")
    print(f"设备位置: {config.device.location}")
    print(f"MQTT Client ID: {config.mqtt.client_id}")
    print()
    
    # 验证设备ID和MQTT Client ID是否一致
    if config.device.id == config.mqtt.client_id:
        print("✅ 设备ID和MQTT Client ID一致")
    else:
        print("❌ 设备ID和MQTT Client ID不一致")
        print(f"   设备ID: {config.device.id}")
        print(f"   MQTT Client ID: {config.mqtt.client_id}")
    print()

def test_id_consistency():
    """测试ID生成的一致性"""
    print("=" * 60)
    print("测试3: ID生成一致性（多次调用应返回相同ID）")
    print("=" * 60)
    
    ids = [get_device_id() for _ in range(5)]
    
    if len(set(ids)) == 1:
        print(f"✅ 多次调用返回相同ID: {ids[0]}")
    else:
        print("❌ 多次调用返回不同ID:")
        for i, device_id in enumerate(ids, 1):
            print(f"   调用{i}: {device_id}")
    print()

if __name__ == "__main__":
    try:
        test_device_id()
        test_config_manager()
        test_id_consistency()
        
        print("=" * 60)
        print("所有测试完成！")
        print("=" * 60)
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
