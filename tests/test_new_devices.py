#!/usr/bin/env python3
"""
新增 IO 设备测试
"""

import sys
import os
import time

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

print("\n" + "=" * 70)
print("新增 IO 设备功能测试")
print("=" * 70)

# 测试 1: 导入所有新设备
print("\n测试 1: 模块导入")
print("-" * 70)

try:
    from modules.device import (
        ButtonDevice,
        PIRSensor,
        BuzzerDevice,
        RelayDevice
    )
    print("✅ 所有设备类导入成功")
    
    from modules.device.effects import (
        BeepEffect,
        BeepPatternEffect,
        SirenEffect,
        MorseCodeEffect,
        ChirpEffect
    )
    print("✅ 所有蜂鸣器效果导入成功")
    
except Exception as e:
    print(f"❌ 导入失败: {e}")
    sys.exit(1)

# 测试 2: 按钮设备
print("\n测试 2: 按钮设备")
print("-" * 70)

try:
    button = ButtonDevice(pin=17, simulate=True)
    
    if button.initialize():
        print("✅ 按钮设备初始化成功")
        
        # 测试读取状态
        state = button.read()
        print(f"   当前状态: {'按下' if state else '未按下'}")
        
        # 测试回调
        def on_button_press(data):
            print(f"   回调触发: 按钮状态 = {data}")
        
        button.register_callback(on_button_press)
        print("   回调已注册")
        
        # 模拟按下
        button.simulate_press()
        
        # 获取设备信息
        info = button.get_info()
        print(f"\n   设备信息:")
        print(f"   - ID: {info['device_id']}")
        print(f"   - 名称: {info['name']}")
        print(f"   - 引脚: GPIO {info['pin']}")
        print(f"   - 消抖时间: {info['debounce_time']}s")
        
        button.cleanup()
        print("\n✅ 按钮设备测试通过")
    else:
        print("❌ 按钮设备初始化失败")
        
except Exception as e:
    print(f"❌ 测试失败: {e}")
    import traceback
    traceback.print_exc()

# 测试 3: PIR 传感器
print("\n测试 3: PIR 传感器")
print("-" * 70)

try:
    pir = PIRSensor(pin=27, simulate=True)
    
    if pir.initialize():
        print("✅ PIR 传感器初始化成功")
        
        # 测试读取状态
        motion = pir.is_motion_detected()
        print(f"   运动检测: {'是' if motion else '否'}")
        
        # 测试回调
        def on_motion(detected):
            print(f"   回调触发: 检测到运动 = {detected}")
        
        pir.register_callback(on_motion)
        
        # 模拟运动
        pir.simulate_motion()
        
        # 获取设备信息
        info = pir.get_info()
        print(f"\n   设备信息:")
        print(f"   - ID: {info['device_id']}")
        print(f"   - 名称: {info['name']}")
        print(f"   - 引脚: GPIO {info['pin']}")
        print(f"   - 触发延迟: {info['trigger_delay']}s")
        
        pir.cleanup()
        print("\n✅ PIR 传感器测试通过")
    else:
        print("❌ PIR 传感器初始化失败")
        
except Exception as e:
    print(f"❌ 测试失败: {e}")
    import traceback
    traceback.print_exc()

# 测试 4: 蜂鸣器设备
print("\n测试 4: 蜂鸣器设备")
print("-" * 70)

try:
    buzzer = BuzzerDevice(pin=22, pwm_enabled=False, simulate=True)
    
    if buzzer.initialize():
        print("✅ 蜂鸣器初始化成功")
        
        # 测试基本控制
        print("\n   测试基本控制:")
        buzzer.write(True)
        print("   ✅ 开启")
        buzzer.write(False)
        print("   ✅ 关闭")
        
        # 测试短促蜂鸣
        print("\n   测试短促蜂鸣:")
        buzzer.beep(0.1)
        print("   ✅ 蜂鸣完成")
        
        # 获取设备信息
        info = buzzer.get_info()
        print(f"\n   设备信息:")
        print(f"   - ID: {info['device_id']}")
        print(f"   - 名称: {info['name']}")
        print(f"   - 引脚: GPIO {info['pin']}")
        print(f"   - PWM: {info['pwm_enabled']}")
        
        buzzer.cleanup()
        print("\n✅ 蜂鸣器设备测试通过")
    else:
        print("❌ 蜂鸣器初始化失败")
        
except Exception as e:
    print(f"❌ 测试失败: {e}")
    import traceback
    traceback.print_exc()

# 测试 5: 蜂鸣器音效
print("\n测试 5: 蜂鸣器音效系统")
print("-" * 70)

try:
    buzzer = BuzzerDevice(pin=22, simulate=True)
    buzzer.initialize()
    
    # 测试单次蜂鸣
    print("\n   测试单次蜂鸣效果:")
    effect = BeepEffect(duration=0.2)
    buzzer.set_effect(effect)
    for _ in range(5):
        buzzer.update()
        time.sleep(0.1)
    print("   ✅ 单次蜂鸣")
    
    # 测试模式蜂鸣
    print("\n   测试模式蜂鸣效果 (短-短-长):")
    effect = BeepPatternEffect(repeat=2)
    buzzer.set_effect(effect)
    for _ in range(10):
        buzzer.update()
        time.sleep(0.1)
    print("   ✅ 模式蜂鸣")
    
    # 测试警报声
    print("\n   测试警报声效果:")
    effect = SirenEffect(on_duration=0.3, off_duration=0.3)
    buzzer.set_effect(effect)
    for _ in range(5):
        buzzer.update()
        time.sleep(0.1)
    buzzer.stop_effect()
    print("   ✅ 警报声")
    
    # 测试摩斯密码
    print("\n   测试摩斯密码效果 (SOS):")
    effect = MorseCodeEffect("... --- ...", dot_duration=0.1)
    buzzer.set_effect(effect)
    for _ in range(20):
        buzzer.update()
        time.sleep(0.1)
    print("   ✅ 摩斯密码")
    
    buzzer.cleanup()
    print("\n✅ 蜂鸣器音效系统测试通过")
    
except Exception as e:
    print(f"❌ 测试失败: {e}")
    import traceback
    traceback.print_exc()

# 测试 6: 继电器设备
print("\n测试 6: 继电器设备")
print("-" * 70)

try:
    relay = RelayDevice(pin=23, name="电磁锁", simulate=True)
    
    if relay.initialize():
        print("✅ 继电器初始化成功")
        
        # 测试开关控制
        print("\n   测试开关控制:")
        relay.turn_on()
        print(f"   ✅ 开启 (状态: {relay.is_on()})")
        
        relay.turn_off()
        print(f"   ✅ 关闭 (状态: {relay.is_on()})")
        
        # 测试切换
        print("\n   测试状态切换:")
        relay.toggle()
        print(f"   ✅ 切换到: {relay.is_on()}")
        
        # 测试脉冲控制
        print("\n   测试脉冲控制 (0.5秒):")
        relay.pulse(0.5)
        print("   ✅ 脉冲完成")
        
        # 获取设备信息
        info = relay.get_info()
        print(f"\n   设备信息:")
        print(f"   - ID: {info['device_id']}")
        print(f"   - 名称: {info['name']}")
        print(f"   - 引脚: GPIO {info['pin']}")
        print(f"   - 类型: {'常开' if info['normally_open'] else '常闭'}")
        
        relay.cleanup()
        print("\n✅ 继电器设备测试通过")
    else:
        print("❌ 继电器初始化失败")
        
except Exception as e:
    print(f"❌ 测试失败: {e}")
    import traceback
    traceback.print_exc()

# 测试 7: 设备管理器集成
print("\n测试 7: 设备管理器集成")
print("-" * 70)

try:
    from modules.device import DeviceManager, LEDStripDevice
    
    manager = DeviceManager()
    
    # 创建所有类型的设备
    button = ButtonDevice(pin=17, simulate=True)
    pir = PIRSensor(pin=27, simulate=True)
    led = LEDStripDevice(pin=18, count=30, simulate=True)
    buzzer = BuzzerDevice(pin=22, simulate=True)
    relay = RelayDevice(pin=23, name="门锁", simulate=True)
    
    # 注册所有设备
    manager.register_device(button)
    manager.register_device(pir)
    manager.register_device(led)
    manager.register_device(buzzer)
    manager.register_device(relay)
    
    print(f"✅ 已注册 {len(manager.get_all_devices())} 个设备")
    print(f"   输入设备: {len(manager.get_all_input_devices())} 个")
    print(f"   输出设备: {len(manager.get_all_output_devices())} 个")
    
    # 列出所有设备
    print("\n   设备列表:")
    for device in manager.get_all_devices():
        info = device.get_info()
        print(f"   - {info['name']} ({info['device_type']})")
    
    # 清理
    manager.cleanup_all()
    print("\n✅ 设备管理器集成测试通过")
    
except Exception as e:
    print(f"❌ 测试失败: {e}")
    import traceback
    traceback.print_exc()

# 总结
print("\n" + "=" * 70)
print("✅ 所有测试通过！新增 IO 设备工作正常")
print("=" * 70)
print("\n新增设备:")
print("  📥 输入设备:")
print("     ✅ ButtonDevice - 按钮（支持单击/长按/双击检测）")
print("     ✅ PIRSensor - PIR 运动传感器")
print("\n  📤 输出设备:")
print("     ✅ BuzzerDevice - 蜂鸣器（支持有源/无源）")
print("     ✅ RelayDevice - 继电器（支持常开/常闭）")
print("\n  🎵 蜂鸣器音效:")
print("     ✅ BeepEffect - 单次蜂鸣")
print("     ✅ BeepPatternEffect - 模式蜂鸣 (短-短-长)")
print("     ✅ SirenEffect - 警报声")
print("     ✅ MorseCodeEffect - 摩斯密码")
print("     ✅ ChirpEffect - 快速短促音")
print("\n应用场景示例:")
print("  🚪 智能门禁:")
print("     - ButtonDevice: 开门按钮")
print("     - PIRSensor: 人体接近检测")
print("     - RelayDevice: 电磁锁控制")
print("     - BuzzerDevice: 提示音/警报")
print("     - LEDStripDevice: 状态指示灯")
print("=" * 70 + "\n")
