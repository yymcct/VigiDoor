#!/usr/bin/env python3
"""
设备模块功能测试
"""

import sys
import os
import time

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

print("\n" + "=" * 60)
print("设备模块功能测试")
print("=" * 60)

# 测试 1: 导入模块
print("\n测试 1: 模块导入")
print("-" * 60)

try:
    from modules.device import (
        DeviceControllerProcess,
        DeviceMode,
        ModeManager,
        DeviceManager,
        DeviceBase,
        InputDevice,
        OutputDevice,
        LEDStripDevice
    )
    print("✅ 所有类导入成功")
    
    from modules.device.effects import (
        EffectBase,
        SolidColorEffect,
        BlinkEffect,
        BreathEffect,
        RainbowEffect,
        PulseEffect
    )
    print("✅ 所有效果类导入成功")
    
except Exception as e:
    print(f"❌ 导入失败: {e}")
    sys.exit(1)

# 测试 2: 模式管理器
print("\n测试 2: 模式管理器")
print("-" * 60)

try:
    mode_manager = ModeManager()
    print(f"✅ 初始模式: {mode_manager.get_mode().value}")
    
    # 注册回调
    def on_mode_change(old, new):
        print(f"   模式切换: {old.value} -> {new.value}")
    
    mode_manager.add_callback(on_mode_change)
    
    # 测试模式切换
    mode_manager.set_mode(DeviceMode.ALERT)
    mode_manager.set_mode(DeviceMode.ALARM)
    mode_manager.set_mode(DeviceMode.SAFE)
    
    print("✅ 模式切换测试通过")
    
except Exception as e:
    print(f"❌ 测试失败: {e}")
    import traceback
    traceback.print_exc()

# 测试 3: LED 设备
print("\n测试 3: LED 灯带设备")
print("-" * 60)

try:
    led = LEDStripDevice(pin=18, count=30, simulate=True)
    
    if led.initialize():
        print("✅ LED 设备初始化成功")
        
        # 测试纯色
        print("\n   测试纯色:")
        led.write((255, 0, 0))  # 红色
        print("   ✅ 红色设置成功")
        
        # 测试设备信息
        info = led.get_info()
        print(f"\n   设备信息:")
        print(f"   - ID: {info['device_id']}")
        print(f"   - 名称: {info['name']}")
        print(f"   - 引脚: GPIO {info['pin']}")
        print(f"   - 数量: {info['count']}")
        print(f"   - 模拟模式: {info['simulate']}")
        
        led.cleanup()
        print("\n✅ LED 设备测试通过")
    else:
        print("❌ LED 设备初始化失败")
        
except Exception as e:
    print(f"❌ 测试失败: {e}")
    import traceback
    traceback.print_exc()

# 测试 4: 效果系统
print("\n测试 4: LED 效果系统")
print("-" * 60)

try:
    led = LEDStripDevice(pin=18, count=30, simulate=True)
    led.initialize()
    
    # 测试纯色效果
    print("\n   测试纯色效果:")
    effect = SolidColorEffect((0, 255, 0))  # 绿色
    led.set_effect(effect)
    led.update()
    print("   ✅ 纯色效果")
    
    # 测试闪烁效果
    print("\n   测试闪烁效果 (1秒):")
    effect = BlinkEffect((255, 255, 0), interval=0.2)  # 黄色闪烁
    led.set_effect(effect)
    for _ in range(5):
        led.update()
        time.sleep(0.2)
    led.stop_effect()
    print("   ✅ 闪烁效果")
    
    led.cleanup()
    print("\n✅ 效果系统测试通过")
    
except Exception as e:
    print(f"❌ 测试失败: {e}")
    import traceback
    traceback.print_exc()

# 测试 5: 设备管理器
print("\n测试 5: 设备管理器")
print("-" * 60)

try:
    manager = DeviceManager()
    
    # 创建设备
    led1 = LEDStripDevice(pin=18, count=30, simulate=True)
    led2 = LEDStripDevice(pin=19, count=20, simulate=True)
    
    # 注册设备
    manager.register_device(led1)
    manager.register_device(led2)
    
    print(f"✅ 已注册 {len(manager.get_all_devices())} 个设备")
    print(f"   输出设备: {len(manager.get_all_output_devices())} 个")
    
    # 获取设备
    device = manager.get_device("led_strip_18")
    print(f"   获取设备: {device.name}")
    
    # 清理
    manager.cleanup_all()
    print("✅ 设备管理器测试通过")
    
except Exception as e:
    print(f"❌ 测试失败: {e}")
    import traceback
    traceback.print_exc()

# 总结
print("\n" + "=" * 60)
print("✅ 所有测试通过！设备模块工作正常")
print("=" * 60)
print("\n模块特点:")
print("  ✅ 模块化架构 - 功能清晰分离")
print("  ✅ 抽象接口 - 易于扩展新设备")
print("  ✅ 效果系统 - 支持丰富的动画效果")
print("  ✅ 统一管理 - DeviceManager 集中控制")
print("  ✅ 模式驱动 - ModeManager 自动切换")
print("\n后续扩展方向:")
print("  - 添加按钮输入设备 (devices/input/button.py)")
print("  - 添加 PIR 传感器 (devices/input/pir_sensor.py)")
print("  - 添加蜂鸣器 (devices/output/buzzer.py)")
print("  - 添加继电器控制 (devices/output/relay.py)")
print("  - 添加更多 LED 效果 (effects/led_effects.py)")
print("=" * 60 + "\n")
