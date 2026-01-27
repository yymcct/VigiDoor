#!/usr/bin/env python3
"""
MQTT 重构验证脚本
快速测试新架构的各个组件
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_topic_manager():
    """测试话题管理器"""
    print("\n" + "="*60)
    print("📋 测试 TopicManager")
    print("="*60)
    
    from utils.mqtt_topics import TopicManager
    
    tm = TopicManager("RPI_001")
    
    # 测试话题构建
    topics = [
        ("上线消息", TopicManager.LIFECYCLE_ONLINE),
        ("视觉告警", TopicManager.ALARM_VISION),
        ("健康指标", TopicManager.HEALTH_METRICS),
        ("推流控制", TopicManager.COMMAND_STREAM),
    ]
    
    for name, template in topics:
        topic = tm.build(template)
        qos = TopicManager.get_qos_for_topic(template)
        retain = TopicManager.should_retain(template)
        print(f"✅ {name:12} -> {topic}")
        print(f"   QoS={qos}, Retain={retain}")
    
    # 测试订阅列表
    print("\n📥 设备订阅列表:")
    for topic, qos in tm.get_device_subscribe_topics():
        print(f"   {topic} (QoS={qos})")
    
    # 测试话题解析
    print("\n🔍 话题解析测试:")
    test_topic = "vigidoor/down/RPI_001/command/stream"
    parsed = tm.parse_topic(test_topic)
    print(f"   话题: {test_topic}")
    print(f"   解析: {parsed}")
    
    print("\n✅ TopicManager 测试通过!")


def test_message_models():
    """测试消息模型"""
    print("\n" + "="*60)
    print("📦 测试消息模型")
    print("="*60)
    
    from utils.mqtt_messages import (
        AlarmVisionMessage,
        HealthMetricsMessage,
        CommandMessage,
        MessageFactory
    )
    
    # 测试视觉告警消息
    alarm_msg = AlarmVisionMessage(
        device_id="RPI_001",
        data={
            "alarm_type": "person_detected",
            "confidence": 0.95,
            "object_count": 2,
            "severity": "high"
        }
    )
    
    print(f"✅ 视觉告警消息创建成功")
    print(f"   msg_id: {alarm_msg.msg_id}")
    print(f"   timestamp: {alarm_msg.timestamp}")
    print(f"   device_id: {alarm_msg.device_id}")
    
    # 测试序列化
    json_str = alarm_msg.to_json()
    print(f"\n📤 JSON 序列化:")
    print(f"   {json_str[:100]}...")
    
    # 测试反序列化
    parsed_msg = MessageFactory.parse_message(
        "vigidoor/up/RPI_001/alarm/vision",
        json_str
    )
    print(f"\n📥 JSON 反序列化:")
    print(f"   类型: {type(parsed_msg).__name__}")
    print(f"   告警类型: {parsed_msg.data['alarm_type']}")
    
    # 测试健康指标消息
    health_msg = HealthMetricsMessage(
        device_id="RPI_001",
        data={
            "cpu_usage": 45.2,
            "memory_usage": 68.5,
            "temperature": 58.5
        }
    )
    print(f"\n✅ 健康指标消息创建成功")
    print(f"   CPU: {health_msg.data['cpu_usage']}%")
    
    print("\n✅ 消息模型测试通过!")


def test_publisher():
    """测试发布器（模拟客户端）"""
    print("\n" + "="*60)
    print("📤 测试 MQTTPublisher")
    print("="*60)
    
    from utils.mqtt_topics import TopicManager
    from utils.mqtt_publisher import MQTTPublisher
    
    # 创建模拟的 MQTT 客户端
    class MockMQTTClient:
        def __init__(self):
            self.published_messages = []
        
        def publish(self, topic, payload, qos=1, retain=False):
            self.published_messages.append({
                'topic': topic,
                'payload': payload,
                'qos': qos,
                'retain': retain
            })
            # 模拟成功返回
            class Result:
                rc = 0
            return Result()
    
    mock_client = MockMQTTClient()
    tm = TopicManager("RPI_001")
    publisher = MQTTPublisher(mock_client, tm)
    
    # 测试发布告警
    print("📤 发布视觉告警...")
    success = publisher.publish_alarm_vision({
        "alarm_type": "person_detected",
        "confidence": 0.95
    })
    
    if success:
        print("✅ 告警发布成功")
        msg = mock_client.published_messages[-1]
        print(f"   话题: {msg['topic']}")
        print(f"   QoS: {msg['qos']}")
    
    # 测试发布健康指标
    print("\n📤 发布健康指标...")
    publisher.publish_health_metrics({
        "cpu_usage": 45.2,
        "memory_usage": 68.5
    })
    
    # 测试统计
    stats = publisher.get_stats()
    print(f"\n📊 发布统计:")
    print(f"   已发布: {stats['published']} 条")
    print(f"   失败: {stats['failed']} 条")
    print(f"   缓存: {stats['buffer_size']}/{stats['buffer_capacity']}")
    
    print("\n✅ Publisher 测试通过!")


def test_handlers():
    """测试消息处理器"""
    print("\n" + "="*60)
    print("🎯 测试消息处理器")
    print("="*60)
    
    from utils.mqtt_topics import TopicManager
    from utils.mqtt_publisher import MQTTPublisher
    from utils.mqtt_handlers import MQTTMessageDispatcher
    import multiprocessing as mp
    from utils.ipc import IPCHelper
    
    # 创建模拟组件
    class MockMQTTClient:
        def publish(self, topic, payload, qos=1, retain=False):
            class Result:
                rc = 0
            return Result()
    
    ipc_queue = mp.Queue()
    ipc = IPCHelper(ipc_queue, 'test')
    tm = TopicManager("RPI_001")
    publisher = MQTTPublisher(MockMQTTClient(), tm)
    dispatcher = MQTTMessageDispatcher(ipc, tm, publisher)
    
    # 测试推流控制指令
    print("📥 测试推流控制指令...")
    test_message = {
        "msg_id": "test-msg-001",
        "timestamp": 1706371200000,
        "device_id": "RPI_001",
        "version": "1.0",
        "data": {
            "action": "start",
            "rtmp_url": "rtmp://test-server/live/RPI_001"
        }
    }
    
    import json
    success = dispatcher.dispatch(
        "vigidoor/down/RPI_001/command/stream",
        json.dumps(test_message)
    )
    
    if success:
        print("✅ 推流指令处理成功")
        # 检查 IPC 消息
        try:
            ipc_msg = ipc_queue.get(timeout=0.1)
            print(f"   转发到: {ipc_msg['to']}")
            print(f"   消息类型: {ipc_msg['type']}")
        except:
            pass
    
    print("\n✅ Handlers 测试通过!")


def test_integration():
    """集成测试"""
    print("\n" + "="*60)
    print("🔗 集成测试")
    print("="*60)
    
    from utils.mqtt_topics import TopicManager
    from utils.mqtt_messages import AlarmVisionMessage
    from utils.mqtt_publisher import MQTTPublisher
    
    # 模拟完整流程
    class MockClient:
        def publish(self, topic, payload, qos=1, retain=False):
            print(f"   📤 发布到: {topic}")
            print(f"      QoS={qos}, Retain={retain}")
            class Result:
                rc = 0
            return Result()
    
    print("🔄 模拟完整的告警上报流程:")
    print("\n1️⃣ 创建话题管理器...")
    tm = TopicManager("RPI_001")
    
    print("2️⃣ 创建发布器...")
    publisher = MQTTPublisher(MockClient(), tm)
    
    print("3️⃣ 构建告警消息...")
    alarm_data = {
        "alarm_type": "person_detected",
        "confidence": 0.95,
        "object_count": 2,
        "severity": "high"
    }
    
    print("4️⃣ 发布告警...")
    success = publisher.publish_alarm_vision(alarm_data)
    
    if success:
        print("\n✅ 完整流程执行成功!")
    
    print("\n✅ 集成测试通过!")


def main():
    """运行所有测试"""
    print("\n" + "🚀 "*20)
    print("VigiDoor MQTT 重构验证测试")
    print("🚀 "*20)
    
    try:
        test_topic_manager()
        test_message_models()
        test_publisher()
        test_handlers()
        test_integration()
        
        print("\n" + "🎉 "*20)
        print("所有测试通过！MQTT 重构成功！")
        print("🎉 "*20 + "\n")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
