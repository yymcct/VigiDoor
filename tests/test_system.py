#!/usr/bin/env python3
"""
VigiDoor 系统测试脚本
用于验证核心功能是否正常
"""

import sys
import os

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

def test_imports():
    """测试模块导入"""
    print("=" * 60)
    print("测试 1: 模块导入")
    print("=" * 60)
    
    try:
        from utils.logger import setup_logger
        print("✅ utils.logger 导入成功")
        
        from core.ipc import IPCClient, MessageBus
        print("✅ core.ipc 导入成功")
        
        import yaml
        print("✅ yaml 导入成功")
        
        import multiprocessing as mp
        print("✅ multiprocessing 导入成功")
        
        print("\n✅ 所有核心模块导入成功！\n")
        return True
        
    except Exception as e:
        print(f"\n❌ 模块导入失败: {e}\n")
        return False


def test_config():
    """测试配置文件"""
    print("=" * 60)
    print("测试 2: 配置文件")
    print("=" * 60)
    
    try:
        import yaml
        
        with open('config.yaml', 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        print(f"✅ 配置文件加载成功")
        print(f"   设备 ID: {config['device']['id']}")
        print(f"   设备名称: {config['device']['name']}")
        print(f"   MQTT Broker: {config['mqtt']['broker_host']}")
        print(f"   流媒体服务器: {config['stream']['zlm_server']}")
        
        print("\n✅ 配置文件测试通过！\n")
        return True
        
    except Exception as e:
        print(f"\n❌ 配置文件测试失败: {e}\n")
        return False


def test_logger():
    """测试日志系统"""
    print("=" * 60)
    print("测试 3: 日志系统")
    print("=" * 60)
    
    try:
        from utils.logger import setup_logger
        
        logger = setup_logger('test')
        logger.info("这是一条测试日志")
        logger.warning("这是一条警告日志")
        
        # 检查日志文件
        if os.path.exists('logs/test.log'):
            print("✅ 日志文件创建成功: logs/test.log")
        else:
            print("⚠️  日志文件未创建")
        
        print("\n✅ 日志系统测试通过！\n")
        return True
        
    except Exception as e:
        print(f"\n❌ 日志系统测试失败: {e}\n")
        return False


def test_ipc():
    """测试进程间通信"""
    print("=" * 60)
    print("测试 4: 进程间通信")
    print("=" * 60)
    
    try:
        from core.ipc import MessageBus, ProcessName
        from core.ipc.message import IPCMessage, MessageType
        
        bus = MessageBus(max_queue_size=10)
        sender = bus.get_client(ProcessName.CAMERA)
        receiver = bus.get_client(ProcessName.SUPERVISOR)
        
        msg = IPCMessage(
            msg_type=MessageType.HEARTBEAT,
            target=ProcessName.SUPERVISOR,
            data={'key': 'value'},
        )
        sender.send_message(msg)
        print("✅ 消息发送成功")
        
        received = receiver.receive(timeout=1)
        if received:
            print(f"✅ 消息接收成功: {received.msg_type}")
        else:
            raise RuntimeError("未收到消息")
        
        bus.close()
        
        print("\n✅ IPC 系统测试通过！\n")
        return True
        
    except Exception as e:
        print(f"\n❌ IPC 系统测试失败: {e}\n")
        return False


def test_process_modules():
    """测试业务进程模块"""
    print("=" * 60)
    print("测试 5: 业务进程模块")
    print("=" * 60)
    
    try:
        from modules.detector_process import AIDetectorProcess
        print("✅ AIDetectorProcess 导入成功")
        
        from modules.mqtt_process import MQTTClientProcess
        print("✅ MQTTClientProcess 导入成功")
        
        from modules.device import DeviceControllerProcess
        print("✅ DeviceControllerProcess 导入成功")
        
        from modules.stream import StreamManagerProcess
        print("✅ StreamManagerProcess 导入成功")
        
        from modules.audio_process import AudioProcessorProcess
        print("✅ AudioProcessorProcess 导入成功")
        
        print("\n✅ 所有业务进程模块导入成功！\n")
        return True
        
    except Exception as e:
        print(f"\n❌ 业务进程模块测试失败: {e}\n")
        return False


def main():
    """运行所有测试"""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 15 + "VigiDoor 系统测试" + " " * 25 + "║")
    print("╚" + "=" * 58 + "╝")
    print("\n")
    
    results = []
    
    # 运行测试
    results.append(("模块导入", test_imports()))
    results.append(("配置文件", test_config()))
    results.append(("日志系统", test_logger()))
    results.append(("IPC 通信", test_ipc()))
    results.append(("业务进程", test_process_modules()))
    
    # 汇总结果
    print("=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{name:12} : {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print("=" * 60)
    print(f"总计: {len(results)} 项测试, {passed} 项通过, {failed} 项失败")
    print("=" * 60)
    
    if failed == 0:
        print("\n🎉 所有测试通过！系统骨架搭建成功！")
        print("\n下一步:")
        print("  1. 运行 supervisor: python3 supervisor.py")
        print("  2. 查看日志: tail -f logs/*.log")
        print("  3. 阅读 QUICKSTART.md 了解更多\n")
        return 0
    else:
        print(f"\n⚠️  有 {failed} 项测试失败，请检查错误信息\n")
        return 1


if __name__ == '__main__':
    sys.exit(main())
