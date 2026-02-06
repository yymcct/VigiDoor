"""
数据库集成示例

展示如何在 Detector 和 Audio 进程中集成数据库写入功能。
这是一个参考实现，展示了集成的关键步骤。

在实际集成时，只需在进程中：
1. 创建 DBWriterHelper 实例
2. 在检测到异常事件时调用 write_event()
"""

from db import DBWriterHelper


# ============================================================
# 示例 1: Detector 进程集成
# ============================================================

class DetectorProcessExample:
    """
    Detector 进程示例 - 展示如何写入视觉检测事件
    
    实际集成位置: modules/detector/process.py
    """
    
    def __init__(self, ipc_client, shared_state, config):
        self.ipc_client = ipc_client
        self.shared_state = shared_state
        self.config = config
        
        # 创建 DB 写入辅助器
        self.db_writer = DBWriterHelper(ipc_client)
    
    def on_intrusion_detected(self, detection_result):
        """
        当检测到入侵时调用
        
        Args:
            detection_result: YOLO 检测结果
                {
                    "confidence": 0.92,
                    "bbox": [x, y, w, h],
                    "class": "person"
                }
        """
        # 判断严重程度
        severity = "high" if detection_result["confidence"] > 0.8 else "medium"
        
        # 写入事件日志
        self.db_writer.write_event(
            event_type="intrusion",
            severity=severity,
            source="detector",
            confidence=detection_result["confidence"],
            detail={
                "bbox": detection_result["bbox"],
                "class": detection_result["class"],
                "timestamp": detection_result.get("timestamp")
            }
        )
        
        print(f"✅ 入侵事件已记录到数据库 (置信度: {detection_result['confidence']})")


# ============================================================
# 示例 2: Audio 进程集成
# ============================================================

class AudioProcessExample:
    """
    Audio 进程示例 - 展示如何写入音频异常事件
    
    实际集成位置: modules/audio_process.py 或 modules/audio/process.py
    """
    
    def __init__(self, ipc_client, shared_state, config):
        self.ipc_client = ipc_client
        self.shared_state = shared_state
        self.config = config
        
        # 创建 DB 写入辅助器
        self.db_writer = DBWriterHelper(ipc_client)
    
    def on_audio_anomaly_detected(self, event_type, confidence, detail=None):
        """
        当检测到音频异常时调用
        
        Args:
            event_type: 事件类型 (glass_breaking/scream/alarm等)
            confidence: 置信度 (0-1)
            detail: 详细信息字典
        """
        # 判断严重程度
        if event_type in ["glass_breaking", "scream", "gunshot"]:
            severity = "high"
        elif event_type in ["alarm", "explosion"]:
            severity = "high"
        else:
            severity = "medium"
        
        # 写入事件日志
        self.db_writer.write_event(
            event_type=event_type,
            severity=severity,
            source="audio",
            confidence=confidence,
            detail=detail
        )
        
        print(f"✅ 音频异常事件已记录到数据库: {event_type} (置信度: {confidence})")
    
    def on_volume_high(self, db_level):
        """
        当音量过高时调用（可选，用于监控异常音量）
        
        Args:
            db_level: 音量分贝值
        """
        self.db_writer.write_event(
            event_type="volume_high",
            severity="low",
            source="audio",
            confidence=1.0,
            detail={"db_level": db_level}
        )


# ============================================================
# 示例 3: MQTT 进程集成 - 配置更新
# ============================================================

class MQTTProcessExample:
    """
    MQTT 进程示例 - 展示如何处理远程配置更新
    
    实际集成位置: modules/mqtt_process.py
    """
    
    def __init__(self, ipc_client, shared_state, config):
        self.ipc_client = ipc_client
        self.shared_state = shared_state
        self.config = config
        
        # 创建 DB 写入辅助器
        self.db_writer = DBWriterHelper(ipc_client)
    
    def on_config_update_from_cloud(self, config_key, config_value):
        """
        当从云端收到配置更新时调用
        
        Args:
            config_key: 配置键 (如 "audio.volume_threshold_db")
            config_value: 配置值
        """
        # 更新数据库配置
        self.db_writer.set_config(config_key, str(config_value))
        
        print(f"✅ 配置已更新到数据库: {config_key} = {config_value}")
        
        # TODO: 同时更新共享状态或发送配置变更通知


# ============================================================
# 集成清单 (Integration Checklist)
# ============================================================

INTEGRATION_CHECKLIST = """
数据库集成清单：

✅ Step 1: 数据库基础设施
   - [x] db/init_db.py (数据库初始化)
   - [x] supervisor/db_manager.py (集中写入层)
   - [x] db/reader.py (只读访问器)
   - [x] db/cached_reader.py (缓存读取器)
   - [x] db/writer_helper.py (写入辅助器)

✅ Step 2: Supervisor 集成
   - [x] 启动 DBManager 线程
   - [x] 处理 DB_WRITE 消息
   - [x] 停止时关闭 DBManager

⏳ Step 3: 子进程写入集成 (需手动完成)
   [ ] modules/detector/process.py
       → 在 __init__ 中创建 DBWriterHelper
       → 在检测到入侵时调用 write_event()
   
   [ ] modules/audio_process.py 或 modules/audio/process.py
       → 在 __init__ 中创建 DBWriterHelper
       → 在检测到音频异常时调用 write_event()
   
   [ ] modules/mqtt_process.py (可选)
       → 处理云端配置更新时调用 set_config()

⏳ Step 4: 读取集成 (按需实现)
   [ ] Stream 进程 (OSD 显示)
       → 使用 CachedDBReader 读取人流统计
       → 显示今日事件数
   
   [ ] Detector 进程 (去重)
       → 使用 DBReader 查询最近事件
       → 避免重复上报



✅ = 已完成  ⏳ = 待实现  [ ] = 需手动集成
"""


if __name__ == "__main__":
    print("=" * 70)
    print("VigiDoor SQLite 集成示例")
    print("=" * 70)
    print(INTEGRATION_CHECKLIST)
    print("\n📖 请参考本文件中的示例代码，在实际进程中集成数据库写入功能。")
