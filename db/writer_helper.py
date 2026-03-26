"""
数据库写入辅助模块

为子进程提供便捷的数据库写入接口，通过 IPC 发送写入请求到 DBManager。

使用示例：
    from db.writer_helper import DBWriterHelper
    
    writer = DBWriterHelper(ipc_client)
    writer.write_event(
        event_type="intrusion",
        severity="high",
        source="detector",
        confidence=0.92,
        detail={"bbox": [0.3, 0.4, 0.2, 0.5]}
    )
"""

import json
import logging
from typing import Dict, Any, Optional
from core.ipc.message import IPCMessage, MessageType

logger = logging.getLogger(__name__)


class DBWriterHelper:
    """
    数据库写入辅助类
    
    封装 IPC 消息发送逻辑，提供友好的写入接口
    """
    
    def __init__(self, ipc_client):
        """
        初始化写入辅助器
        
        Args:
            ipc_client: IPC 客户端实例
        """
        self.ipc_client = ipc_client
    
    def _send_db_message(self, action: str, data: Dict[str, Any]) -> bool:
        """
        发送数据库写入消息
        
        Args:
            action: 写入动作 (write_event/write_metric/set_config/cleanup)
            data: 数据字典
            
        Returns:
            是否发送成功
        """
        try:
            msg = IPCMessage(
                msg_type=MessageType.DB_WRITE,
                data={
                    "action": action,
                    **data
                }
            )
            msg.target = "supervisor"
            self.ipc_client.send_message(msg)
            logger.debug(f"DB写入请求已发送: {action}")
            return True
        except Exception as e:
            logger.error(f"发送DB写入请求失败 [{action}]: {e}")
            return False
    
    # ==================== 事件写入 ====================
    
    def write_event(
        self,
        event_type: str,
        severity: str,
        source: str,
        confidence: Optional[float] = None,
        detail: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        写入事件日志
        
        Args:
            event_type: 事件类型 (intrusion/glass_breaking/scream等)
            severity: 严重程度 (low/medium/high)
            source: 来源 (detector/audio)
            confidence: 置信度 (0-1)
            detail: 详细信息字典（会被序列化为JSON）
            
        Returns:
            是否发送成功
            
        Example:
            writer.write_event(
                event_type="intrusion",
                severity="high",
                source="detector",
                confidence=0.92,
                detail={"bbox": [0.3, 0.4, 0.2, 0.5]}
            )
        """
        data = {
            "event_type": event_type,
            "severity": severity,
            "source": source,
        }
        
        if confidence is not None:
            data["confidence"] = confidence
        
        if detail is not None:
            data["detail"] = json.dumps(detail, ensure_ascii=False)
        
        return self._send_db_message("write_event", {"data": data})
    
    # ==================== 统计写入 (预留) ====================
    
    def write_metric(
        self,
        metric_type: str,
        value: Any,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        写入统计数据 (预留)
        
        Args:
            metric_type: 指标类型
            value: 指标值
            metadata: 元数据
            
        Returns:
            是否发送成功
        """
        data = {
            "metric_type": metric_type,
            "value": value,
        }
        
        if metadata is not None:
            data["metadata"] = metadata
        
        return self._send_db_message("write_metric", {"data": data})
    
    # ==================== 配置更新 ====================
    
    def set_config(self, key: str, value: str) -> bool:
        """
        更新配置项
        
        Args:
            key: 配置键 (点号分隔的层级，如 "audio.volume_threshold_db")
            value: 配置值 (字符串)
            
        Returns:
            是否发送成功
            
        Example:
            writer.set_config("audio.volume_threshold_db", "55.0")
        """
        return self._send_db_message("set_config", {"key": key, "value": value})
    
    # ==================== 布撤防记录写入 ====================

    def write_arm_disarm(
        self,
        action: str,
        source: str,
        operator: Optional[str] = None
    ) -> bool:
        """
        写入布撤防操作记录

        Args:
            action: 动作类型，'arm'（布防）或 'disarm'（撤防）
            source: 触发来源，如 'mqtt'、'local'、'api'
            operator: 操作者标识（可选）

        Returns:
            是否发送成功
        """
        import time as _time
        data: Dict[str, Any] = {
            "action": action,
            "source": source,
            "ts": _time.time(),
        }
        if operator is not None:
            data["operator"] = operator
        return self._send_db_message("write_arm_disarm", {"data": data})

    # ==================== 录像片段索引写入 ====================

    def write_recording_start(self, file_path: str, start_time: float) -> bool:
        """
        录像片段开始：在 recording_clips 表中插入新行

        Args:
            file_path: 录像文件绝对/相对路径（唯一标识）
            start_time: 片段开始的 Unix 时间戳

        Returns:
            是否发送成功
        """
        return self._send_db_message("write_recording_start", {
            "data": {"file_path": file_path, "start_time": start_time}
        })

    def finalize_recording_clip(
        self,
        file_path: str,
        end_time: float,
        file_size_bytes: int
    ) -> bool:
        """
        录像片段结束：更新结束时间、时长和文件大小

        Args:
            file_path: 录像文件路径（对应 write_recording_start 中的 file_path）
            end_time: 片段结束的 Unix 时间戳
            file_size_bytes: 文件字节数

        Returns:
            是否发送成功
        """
        return self._send_db_message("finalize_recording_clip", {
            "data": {
                "file_path": file_path,
                "end_time": end_time,
                "file_size_bytes": file_size_bytes,
            }
        })

    def tag_clip_alarm(self, file_path: str, alarm_level: str) -> bool:
        """
        为录像片段打上报警标签

        Args:
            file_path: 录像文件路径
            alarm_level: 报警等级，'alert' 或 'alarm'

        Returns:
            是否发送成功
        """
        return self._send_db_message("tag_clip_alarm", {
            "data": {"file_path": file_path, "alarm_level": alarm_level}
        })

    # ==================== 触发清理 ====================

    def trigger_cleanup(self) -> bool:
        """
        触发数据库清理任务（手动触发，通常不需要）
        
        Returns:
            是否发送成功
        """
        return self._send_db_message("cleanup", {})


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 模拟 IPC 客户端
    class MockIPCClient:
        def send(self, msg):
            print(f"发送消息: {msg.type} - {msg.data}")
    
    # 测试写入
    writer = DBWriterHelper(MockIPCClient())
    
    print("\n=== 测试事件写入 ===")
    writer.write_event(
        event_type="intrusion",
        severity="high",
        source="detector",
        confidence=0.92,
        detail={"bbox": [0.3, 0.4, 0.2, 0.5]}
    )
    
    print("\n=== 测试配置更新 ===")
    writer.set_config("audio.volume_threshold_db", "55.0")
    
    print("\n测试完成")
