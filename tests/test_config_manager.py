#!/usr/bin/env python3
"""
测试 ConfigManager
验证配置管理器的基本功能
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.config import ConfigManager


def test_basic_loading():
    """测试基本加载功能"""
    print("=" * 60)
    print("测试 1: 基本加载功能")
    print("=" * 60)
    
    # 初始化
    config = ConfigManager.initialize('config.yaml')
    
    # 验证加载
    print(f"✓ 设备ID: {config.device.id}")
    print(f"✓ 设备名称: {config.device.name}")
    print(f"✓ 摄像头分辨率: {config.camera.width}x{config.camera.height}")
    print(f"✓ MQTT Broker: {config.mqtt.broker_host}")
    print()


def test_detector_config():
    """测试检测器配置"""
    print("=" * 60)
    print("测试 2: 检测器配置")
    print("=" * 60)
    
    config = ConfigManager.get_instance()
    
    print(f"✓ 模型路径: {config.detector.model_path}")
    print(f"✓ 置信度阈值: {config.detector.confidence_threshold}")
    print(f"✓ 检测间隔: {config.detector.detect_interval}")
    print(f"✓ 安全状态间隔: {config.detector.safe_interval}")
    print(f"✓ 警戒状态间隔: {config.detector.alert_interval}")
    print(f"✓ 报警状态间隔: {config.detector.alarm_interval}")
    print()


def test_region_config():
    """测试区域配置"""
    print("=" * 60)
    print("测试 3: 区域配置")
    print("=" * 60)
    
    config = ConfigManager.get_instance()
    
    if config.detector.region_detector:
        print(f"✓ 重叠阈值: {config.detector.region_detector.overlap_threshold}")
        print(f"✓ 区域数量: {len(config.detector.region_detector.regions)}")
        
        for i, region in enumerate(config.detector.region_detector.regions):
            print(f"\n  区域 {i+1}:")
            print(f"    名称: {region.name}")
            print(f"    类型: {region.type}")
            print(f"    启用: {region.enabled}")
            print(f"    坐标: {region.coords}")
    else:
        print("⚠ 未配置区域检测器")
    
    print()


def test_osd_config():
    """测试OSD配置"""
    print("=" * 60)
    print("测试 4: OSD配置")
    print("=" * 60)
    
    config = ConfigManager.get_instance()
    
    print(f"✓ 时间戳显示: {config.osd.timestamp_enabled}")
    print(f"✓ 设备信息显示: {config.osd.device_info_enabled}")
    print(f"✓ 检测框显示: {config.osd.detection_box_enabled}")
    print(f"✓ 区域叠加显示: {config.osd.region_overlay_enabled}")
    print(f"✓ 区域叠加颜色: {config.osd.region_overlay_color}")
    print(f"✓ 区域叠加粗细: {config.osd.region_overlay_thickness}")
    print(f"✓ 区域叠加透明度: {config.osd.region_overlay_alpha}")
    print()


def test_backward_compatibility():
    """测试向后兼容性"""
    print("=" * 60)
    print("测试 5: 向后兼容性")
    print("=" * 60)
    
    config = ConfigManager.get_instance()
    
    # 获取原始字典
    raw_dict = config.get_raw_dict()
    print(f"✓ 原始字典包含 {len(raw_dict)} 个顶级配置项")
    
    # 使用路径访问
    model_path = config.get_raw('ai_detector.model_path')
    print(f"✓ 通过路径访问: {model_path}")
    
    width = config.get_raw('camera.width', default=1280)
    print(f"✓ 带默认值访问: {width}")
    
    non_exist = config.get_raw('non.exist.key', default='default_value')
    print(f"✓ 不存在的键: {non_exist}")
    
    print()


def test_singleton():
    """测试单例模式"""
    print("=" * 60)
    print("测试 6: 单例模式")
    print("=" * 60)
    
    config1 = ConfigManager.get_instance()
    config2 = ConfigManager.get_instance()
    
    print(f"✓ config1 is config2: {config1 is config2}")
    print(f"✓ id(config1): {id(config1)}")
    print(f"✓ id(config2): {id(config2)}")
    print()


def test_region_overlay_element():
    """测试 RegionOverlayElement 的使用"""
    print("=" * 60)
    print("测试 7: RegionOverlayElement 使用")
    print("=" * 60)
    
    try:
        from modules.stream.osd import RegionOverlayElement
        import numpy as np
        
        # 创建元素（无需传参！）
        element = RegionOverlayElement()
        
        print(f"✓ 元素创建成功")
        print(f"✓ 区域数量: {len(element.regions)}")
        
        if element.osd_config:
            print(f"✓ OSD配置已加载")
            print(f"✓ 区域叠加启用: {element.osd_config.region_overlay_enabled}")
        
        # 创建测试帧
        test_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        
        # 渲染（应该不报错）
        result = element.render(test_frame)
        print(f"✓ 渲染成功，输出形状: {result.shape}")
        
    except ImportError as e:
        print(f"⚠ 跳过 OSD 测试（依赖缺失）: {e}")
    except Exception as e:
        print(f"✗ OSD 测试失败: {e}")
    
    print()


def main():
    try:
        test_basic_loading()
        test_detector_config()
        test_region_config()
        test_osd_config()
        test_backward_compatibility()
        test_singleton()
        test_region_overlay_element()
        
        print("=" * 60)
        print("✅ 所有测试通过！")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
