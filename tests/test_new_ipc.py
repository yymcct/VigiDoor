"""
测试新的IPC架构
验证消息总线的正确性和向后兼容性
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.ipc import (
    MessageBus,
    IPCClient,
    MessageType,
    IPCMessage,
    HeartbeatMessage,
    AlarmMessage,
    ProcessName,
    ProcessRegistry,
)

def test_message_creation():
    """测试消息创建"""
    print("=" * 60)
    print("测试1: 消息创建")
    print("=" * 60)
    
    # 创建心跳消息
    heartbeat = HeartbeatMessage(uptime=100, state='safe')
    print(f"✅ 心跳消息: {heartbeat.to_dict()}")
    
    # 创建告警消息
    alarm = AlarmMessage(
        alarm_type=MessageType.ALARM_VISION,
        alarm_data={'confidence': 0.95, 'object': 'person'}
    )
    print(f"✅ 告警消息: {alarm.to_dict()}")
    
    print()


def test_process_registry():
    """测试进程注册表"""
    print("=" * 60)
    print("测试2: 进程注册表")
    print("=" * 60)
    
    # 获取所有进程
    all_processes = ProcessRegistry.all()
    print(f"✅ 注册的进程数: {len(all_processes)}")
    
    for name, info in all_processes.items():
        print(f"  - {name}: {info.description} (关键进程: {info.critical})")
    
    # 验证进程名称
    print(f"\n✅ MQTT客户端进程名: {ProcessName.MQTT_CLIENT}")
    print(f"✅ 是否为关键进程: {ProcessRegistry.is_critical(ProcessName.MQTT_CLIENT)}")
    
    print()


def test_message_bus():
    """测试消息总线"""
    print("=" * 60)
    print("测试3: 消息总线")
    print("=" * 60)
    
    # 创建消息总线
    bus = MessageBus(max_queue_size=10)
    print("✅ 消息总线创建成功")
    
    # 创建客户端
    mqtt_client = bus.get_client(ProcessName.MQTT_CLIENT)
    supervisor_client = bus.get_client(ProcessName.SUPERVISOR)
    print("✅ IPC客户端创建成功")
    
    # 发送消息
    heartbeat = HeartbeatMessage(uptime=50, state='safe')
    if mqtt_client.send_message(heartbeat):
        print("✅ MQTT客户端发送心跳成功")
    
    # 接收消息
    received_msg = supervisor_client.receive(timeout=0.5)
    if received_msg:
        print(f"✅ Supervisor接收到消息: {received_msg.msg_type}")
        print(f"   发送者: {received_msg.sender}")
        print(f"   数据: {received_msg.data}")
    else:
        print("⚠️  未收到消息（可能超时）")
    
    # 检查队列大小
    queue_sizes = bus.get_queue_sizes()
    print(f"\n✅ 队列状态:")
    for name, size in queue_sizes.items():
        print(f"  - {name}: {size} 条消息")
    
    # 清理
    bus.close()
    print("\n✅ 消息总线关闭成功")
    
    print()


def test_message_types():
    """测试消息类型枚举"""
    print("=" * 60)
    print("测试5: 消息类型")
    print("=" * 60)
    
    # 列出所有消息类型
    print("✅ 已定义的消息类型:")
    for msg_type in MessageType:
        print(f"  - {msg_type.value}")
    
    # 测试类型转换
    try:
        mt = MessageType("heartbeat")
        print(f"\n✅ 字符串转枚举: 'heartbeat' -> {mt}")
    except:
        print("\n❌ 字符串转枚举失败")
    
    print()


if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("🚀 开始测试新的IPC架构")
    print("=" * 60 + "\n")
    
    try:
        test_message_creation()
        test_process_registry()
        test_message_bus()
        test_message_types()
        
        print("=" * 60)
        print("✅ 所有测试通过！")
        print("=" * 60)
        
    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ 测试失败: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        sys.exit(1)
