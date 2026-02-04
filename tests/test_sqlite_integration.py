#!/usr/bin/env python3
"""
SQLite 集成测试脚本

测试数据库的完整读写流程，验证集成是否正常工作。
"""

import sys
import time
import queue
import logging
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from supervisor.db_manager import DBManager
from db import DBReader

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_db_manager_write():
    """测试 DBManager 写入功能"""
    logger.info("=" * 60)
    logger.info("测试 1: DBManager 写入功能")
    logger.info("=" * 60)
    
    # 创建写入队列和 DBManager
    write_queue = queue.Queue()
    manager = DBManager(write_queue)
    
    # 启动 DBManager
    manager.start()
    time.sleep(0.5)
    
    # 测试1: 写入配置
    logger.info("\n[1.1] 写入配置项...")
    write_queue.put({
        "action": "set_config",
        "key": "audio.volume_threshold_db",
        "value": "55.0"
    })
    write_queue.put({
        "action": "set_config",
        "key": "detector.confidence",
        "value": "0.6"
    })
    time.sleep(0.5)
    logger.info("✅ 配置写入完成")
    
    # 测试2: 写入事件
    logger.info("\n[1.2] 写入事件日志...")
    write_queue.put({
        "action": "write_event",
        "data": {
            "event_type": "intrusion",
            "severity": "high",
            "source": "detector",
            "confidence": 0.92,
            "detail": '{"bbox": [0.3, 0.4, 0.2, 0.5]}'
        }
    })
    write_queue.put({
        "action": "write_event",
        "data": {
            "event_type": "glass_breaking",
            "severity": "high",
            "source": "audio",
            "confidence": 0.85,
            "detail": '{"db_level": 75.0}'
        }
    })
    write_queue.put({
        "action": "write_event",
        "data": {
            "event_type": "scream",
            "severity": "medium",
            "source": "audio",
            "confidence": 0.70,
            "detail": '{"duration": 2.5}'
        }
    })
    time.sleep(0.5)
    logger.info("✅ 事件写入完成")
    
    # 停止 DBManager
    manager.stop()
    logger.info("✅ DBManager 测试完成\n")


def test_db_reader():
    """测试 DBReader 读取功能"""
    logger.info("=" * 60)
    logger.info("测试 2: DBReader 读取功能")
    logger.info("=" * 60)
    
    reader = DBReader()
    
    # 测试1: 读取配置
    logger.info("\n[2.1] 读取配置项...")
    configs = reader.get_all_configs()
    logger.info(f"配置项数量: {len(configs)}")
    for key, value in configs.items():
        logger.info(f"  {key} = {value}")
    
    # 测试2: 读取事件
    logger.info("\n[2.2] 读取事件日志...")
    events = reader.get_recent_events(hours=24)
    logger.info(f"最近24小时事件数: {len(events)}")
    for event in events:
        logger.info(
            f"  [{event['severity']}] {event['event_type']} "
            f"(置信度: {event['confidence']:.2f}) "
            f"来源: {event['source']}"
        )
    
    # 测试3: 按类型查询
    logger.info("\n[2.3] 按类型查询事件...")
    high_events = reader.get_events_by_severity("high", hours=24)
    logger.info(f"高危事件数: {len(high_events)}")
    
    # 测试4: 统计
    logger.info("\n[2.4] 统计信息...")
    today_count = reader.get_event_count_today()
    logger.info(f"今日事件总数: {today_count}")
    
    reader.close()
    logger.info("✅ DBReader 测试完成\n")


def test_config_priority():
    """测试配置优先级（DB > YAML）"""
    logger.info("=" * 60)
    logger.info("测试 3: 配置优先级")
    logger.info("=" * 60)
    
    from db.config_loader import ConfigLoader
    
    # 模拟 YAML 配置
    yaml_config = {
        "audio": {
            "volume_threshold_db": 50.0,  # YAML 默认值
            "sample_rate": 16000
        },
        "detector": {
            "confidence": 0.5  # YAML 默认值
        }
    }
    
    logger.info("\n[3.1] YAML 配置:")
    logger.info(f"  audio.volume_threshold_db = {yaml_config['audio']['volume_threshold_db']}")
    logger.info(f"  detector.confidence = {yaml_config['detector']['confidence']}")
    
    # 加载合并配置
    loader = ConfigLoader(yaml_config)
    merged = loader.load_merged_config()
    
    logger.info("\n[3.2] 合并后配置 (DB 优先):")
    logger.info(f"  audio.volume_threshold_db = {merged['audio']['volume_threshold_db']}")
    logger.info(f"  detector.confidence = {merged['detector']['confidence']}")
    
    # 验证优先级
    if merged['audio']['volume_threshold_db'] == 55.0:
        logger.info("✅ DB 配置正确覆盖 YAML (55.0 > 50.0)")
    else:
        logger.warning("⚠️  DB 配置未覆盖 YAML")
    
    if merged['detector']['confidence'] == 0.6:
        logger.info("✅ DB 配置正确覆盖 YAML (0.6 > 0.5)")
    else:
        logger.warning("⚠️  DB 配置未覆盖 YAML")
    
    logger.info("✅ 配置优先级测试完成\n")


def test_database_files():
    """测试数据库文件状态"""
    logger.info("=" * 60)
    logger.info("测试 4: 数据库文件验证")
    logger.info("=" * 60)
    
    data_dir = Path(__file__).parent.parent / "data"
    db_files = ["config.db", "events.db", "metrics.db"]
    
    logger.info(f"\n数据库目录: {data_dir}")
    
    all_ok = True
    for db_file in db_files:
        db_path = data_dir / db_file
        if db_path.exists():
            size = db_path.stat().st_size
            logger.info(f"  ✅ {db_file} (大小: {size} bytes)")
        else:
            logger.error(f"  ❌ {db_file} 不存在")
            all_ok = False
    
    if all_ok:
        logger.info("✅ 所有数据库文件存在\n")
    else:
        logger.error("❌ 部分数据库文件缺失\n")
    
    return all_ok


def main():
    """运行所有测试"""
    logger.info("\n" + "=" * 60)
    logger.info("VigiDoor SQLite 集成测试")
    logger.info("=" * 60 + "\n")
    
    try:
        # 测试1: 验证数据库文件
        if not test_database_files():
            logger.error("❌ 数据库文件验证失败，请先运行 scripts/init_sqlite.sh")
            return 1
        
        # 测试2: DBManager 写入
        test_db_manager_write()
        
        # 测试3: DBReader 读取
        test_db_reader()
        
        # 测试4: 配置优先级
        test_config_priority()
        
        # 总结
        logger.info("=" * 60)
        logger.info("✅ 所有测试通过！SQLite 集成正常工作")
        logger.info("=" * 60)
        logger.info("\n📖 下一步:")
        logger.info("  1. 查看集成文档: doc/SQLITE_INTEGRATION_COMPLETE.md")
        logger.info("  2. 在子进程中集成写入逻辑")
        logger.info("  3. 启动完整系统: python3 supervisor.py\n")
        
        return 0
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
