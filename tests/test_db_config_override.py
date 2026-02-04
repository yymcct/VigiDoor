#!/usr/bin/env python3
"""
测试数据库配置覆盖功能

测试流程：
1. 向配置数据库插入测试配置
2. 启动 ConfigManager（会自动从 DB 加载）
3. 验证配置是否被正确覆盖
"""

import sys
import sqlite3
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.init_db import init_databases
from utils.config import ConfigManager


def setup_test_db_configs():
    """在数据库中插入测试配置"""
    db_dir = Path(__file__).parent.parent / "data"
    db_dir.mkdir(parents=True, exist_ok=True)
    
    # 确保数据库存在
    init_databases(db_dir)
    
    # 连接到配置数据库
    conn = sqlite3.connect(str(db_dir / "config.db"))
    
    # 插入测试配置
    test_configs = [
        # 检测器配置
        ("ai_detector.confidence_threshold", "0.75"),
        ("ai_detector.detect_interval", "10"),
        ("ai_detector.alarm_cooldown", "8.5"),
        
        # 音频配置
        ("audio.anomaly_threshold", "0.85"),
        
        # OSD 开关
        ("osd.timestamp_enabled", "false"),
        ("osd.detection_box_enabled", "true"),
        
        # 监控阈值
        ("monitoring.thresholds.cpu_percent", "85.0"),
        ("monitoring.thresholds.memory_percent", "90.0"),
        
        # 进程管理
        ("supervisor.alarm_auto_reset_seconds", "120"),
    ]
    
    for key, value in test_configs:
        conn.execute(
            "INSERT OR REPLACE INTO kv_config (key, value) VALUES (?, ?)",
            (key, value)
        )
    
    conn.commit()
    conn.close()
    
    print("✅ 测试配置已写入数据库")
    print(f"   共插入 {len(test_configs)} 项配置")


def test_config_override():
    """测试配置覆盖功能"""
    print("\n" + "="*60)
    print("🧪 开始测试配置覆盖功能")
    print("="*60)
    
    # 重置单例（测试环境）
    ConfigManager.reset()
    
    # 初始化 ConfigManager（会自动从 DB 加载）
    config = ConfigManager.initialize("./config.yaml")
    
    print("\n📋 验证配置覆盖结果：")
    print("-" * 60)
    
    # 验证检测器配置
    assert config.detector.confidence_threshold == 0.75, \
        f"预期 0.75, 实际 {config.detector.confidence_threshold}"
    print(f"✓ ai_detector.confidence_threshold = {config.detector.confidence_threshold}")
    
    assert config.detector.detect_interval == 10, \
        f"预期 10, 实际 {config.detector.detect_interval}"
    print(f"✓ ai_detector.detect_interval = {config.detector.detect_interval}")
    
    assert config.detector.alarm_cooldown == 8.5, \
        f"预期 8.5, 实际 {config.detector.alarm_cooldown}"
    print(f"✓ ai_detector.alarm_cooldown = {config.detector.alarm_cooldown}")
    
    # 验证音频配置
    assert config.audio.anomaly_threshold == 0.85, \
        f"预期 0.85, 实际 {config.audio.anomaly_threshold}"
    print(f"✓ audio.anomaly_threshold = {config.audio.anomaly_threshold}")
    
    # 验证 OSD 配置
    assert config.osd.timestamp_enabled == False, \
        f"预期 False, 实际 {config.osd.timestamp_enabled}"
    print(f"✓ osd.timestamp_enabled = {config.osd.timestamp_enabled}")
    
    assert config.osd.detection_box_enabled == True, \
        f"预期 True, 实际 {config.osd.detection_box_enabled}"
    print(f"✓ osd.detection_box_enabled = {config.osd.detection_box_enabled}")
    
    # 验证监控配置
    cpu_threshold = config.monitoring.thresholds.get('cpu_percent')
    assert cpu_threshold == 85.0, \
        f"预期 85.0, 实际 {cpu_threshold}"
    print(f"✓ monitoring.thresholds.cpu_percent = {cpu_threshold}")
    
    memory_threshold = config.monitoring.thresholds.get('memory_percent')
    assert memory_threshold == 90.0, \
        f"预期 90.0, 实际 {memory_threshold}"
    print(f"✓ monitoring.thresholds.memory_percent = {memory_threshold}")
    
    # 验证进程管理配置
    assert config.supervisor.alarm_auto_reset_seconds == 120, \
        f"预期 120, 实际 {config.supervisor.alarm_auto_reset_seconds}"
    print(f"✓ supervisor.alarm_auto_reset_seconds = {config.supervisor.alarm_auto_reset_seconds}")
    
    print("\n" + "="*60)
    print("🎉 所有测试通过！配置覆盖功能正常工作")
    print("="*60)


def cleanup_test_configs():
    """清理测试配置（可选）"""
    db_dir = Path(__file__).parent.parent / "data"
    config_db = db_dir / "config.db"
    
    if config_db.exists():
        conn = sqlite3.connect(str(config_db))
        conn.execute("DELETE FROM kv_config")
        conn.commit()
        conn.close()
        print("\n🧹 测试配置已清理")


if __name__ == "__main__":
    try:
        # 1. 设置测试配置
        setup_test_db_configs()
        
        # 2. 测试配置覆盖
        test_config_override()
        
        # 3. 清理（可选，取消注释以清理）
        # cleanup_test_configs()
        
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
