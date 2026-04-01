"""
DBReader - 只读访问器 (L2层)

各子进程独立实例化，直接从本地数据库读取数据。
WAL模式下多进程并发读是安全的，不会阻塞写入。

使用场景：
- 查询历史事件
- 读取统计数据
- 按需查询（非高频）
"""

import sqlite3
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class DBReader:
    """
    数据库只读访问器
    
    每个子进程独立创建实例，直接读取数据库文件
    """
    
    # 数据库文件目录
    DB_DIR = Path(__file__).parent.parent / "data"
    
    def __init__(self):
        """初始化只读访问器"""
        self._connections: Dict[str, sqlite3.Connection] = {}
    
    def _get_conn(self, db_name: str) -> sqlite3.Connection:
        """
        获取数据库连接 (懒初始化)
        
        Args:
            db_name: 数据库名称 (config/events/metrics)
            
        Returns:
            数据库连接对象
        """
        if db_name not in self._connections:
            db_path = self.DB_DIR / f"{db_name}.db"
            
            if not db_path.exists():
                logger.warning(f"数据库文件不存在: {db_path}")
                # 返回内存数据库，避免崩溃
                conn = sqlite3.connect(":memory:")
            else:
                conn = sqlite3.connect(str(db_path))
            
            # 配置只读模式
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA query_only=ON")  # ← 强制只读
            conn.row_factory = sqlite3.Row  # 返回字典式行对象
            
            self._connections[db_name] = conn
            logger.debug(f"已连接到数据库: {db_name}.db (只读)")
        
        return self._connections[db_name]
    
    def close(self) -> None:
        """关闭所有连接"""
        for conn in self._connections.values():
            conn.close()
        self._connections.clear()
        logger.debug("所有数据库连接已关闭")
    
    # ==================== 配置读取 ====================
    
    def get_config(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        获取配置项
        
        Args:
            key: 配置键
            default: 默认值
            
        Returns:
            配置值，不存在时返回默认值
        """
        try:
            conn = self._get_conn("config")
            cursor = conn.execute(
                "SELECT value FROM kv_config WHERE key = ?",
                (key,)
            )
            row = cursor.fetchone()
            return row["value"] if row else default
        except Exception as e:
            logger.error(f"读取配置失败 [{key}]: {e}")
            return default
    
    def get_all_configs(self) -> Dict[str, str]:
        """
        获取所有配置项
        
        Returns:
            配置字典 {key: value}
        """
        try:
            conn = self._get_conn("config")
            cursor = conn.execute("SELECT key, value FROM kv_config")
            return {row["key"]: row["value"] for row in cursor.fetchall()}
        except Exception as e:
            logger.error(f"读取所有配置失败: {e}")
            return {}
    
    # TODO
    def get_device_info(self, device_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        获取设备信息
        
        Args:
            device_id: 设备ID，不提供则返回第一个设备
            
        Returns:
            设备信息字典
        """
        try:
            conn = self._get_conn("config")
            
            if device_id:
                cursor = conn.execute(
                    "SELECT * FROM device_info WHERE device_id = ?",
                    (device_id,)
                )
            else:
                cursor = conn.execute("SELECT * FROM device_info LIMIT 1")
            
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"读取设备信息失败: {e}")
            return None
    
    # ==================== 事件查询 ====================
    
    def get_recent_events(
        self,
        hours: int = 24,
        event_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        获取最近的事件
        
        Args:
            hours: 时间范围（小时）
            event_type: 事件类型过滤（可选）
            limit: 最大返回数量
            
        Returns:
            事件列表
        """
        try:
            conn = self._get_conn("events")
            
            sql = "SELECT * FROM events WHERE created >= datetime('now', 'localtime', ?)"
            args = [f"-{hours} hours"]
            
            if event_type:
                sql += " AND event_type = ?"
                args.append(event_type)
            
            sql += " ORDER BY created DESC LIMIT ?"
            args.append(limit)
            
            cursor = conn.execute(sql, args)
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"查询最近事件失败: {e}")
            return []
    
    def get_event_count_today(self) -> int:
        """
        获取今天的事件总数
        
        Returns:
            事件数量
        """
        try:
            conn = self._get_conn("events")
            cursor = conn.execute(
                "SELECT COUNT(*) as count FROM events WHERE DATE(created) = DATE('now', 'localtime')"
            )
            row = cursor.fetchone()
            return row["count"] if row else 0
        except Exception as e:
            logger.error(f"查询今日事件数失败: {e}")
            return 0
    
    def get_events_by_severity(
        self,
        severity: str,
        hours: int = 24,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        按严重程度查询事件
        
        Args:
            severity: 严重程度 (low/medium/high)
            hours: 时间范围（小时）
            limit: 最大返回数量
            
        Returns:
            事件列表
        """
        try:
            conn = self._get_conn("events")
            cursor = conn.execute(
                """SELECT * FROM events 
                   WHERE severity = ? 
                   AND created >= datetime('now', 'localtime', ?)
                   ORDER BY created DESC 
                   LIMIT ?""",
                (severity, f"-{hours} hours", limit)
            )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"按严重程度查询事件失败: {e}")
            return []
    
    # ==================== 布撤防查询 ====================

    def get_last_arm_status(self) -> Optional[str]:
        """
        获取最后一次布撤防状态

        Returns:
            'arm'（已布防）或 'disarm'（已撤防），无记录时返回 None
        """
        try:
            conn = self._get_conn("events")
            cursor = conn.execute(
                "SELECT action FROM arm_disarm_log ORDER BY ts DESC LIMIT 1"
            )
            row = cursor.fetchone()
            return row["action"] if row else None
        except Exception as e:
            logger.error(f"读取布撤防状态失败: {e}")
            return None

    # ==================== 统计查询 (预留) ====================
    
    def get_people_stats(
        self,
        hours: int = 24
    ) -> Dict[str, int]:
        """
        获取人流统计 (预留)
        
        Args:
            hours: 时间范围（小时）
            
        Returns:
            统计结果 {"total_in": 0, "total_out": 0, "peak": 0}
        """
        try:
            conn = self._get_conn("metrics")
            cursor = conn.execute(
                """SELECT 
                       SUM(count_in) as total_in,
                       SUM(count_out) as total_out,
                       MAX(count_peak) as peak
                   FROM people_count
                   WHERE window_start >= datetime('now', 'localtime', ?)""",
                (f"-{hours} hours",)
            )
            row = cursor.fetchone()
            
            if row:
                return {
                    "total_in": row["total_in"] or 0,
                    "total_out": row["total_out"] or 0,
                    "peak": row["peak"] or 0
                }
            else:
                return {"total_in": 0, "total_out": 0, "peak": 0}
        except Exception as e:
            logger.error(f"查询人流统计失败: {e}")
            return {"total_in": 0, "total_out": 0, "peak": 0}
    
    def get_audio_metrics(
        self,
        hours: int = 24,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        获取音频指标历史 (预留)
        
        Args:
            hours: 时间范围（小时）
            limit: 最大返回数量
            
        Returns:
            音频指标列表
        """
        try:
            conn = self._get_conn("metrics")
            cursor = conn.execute(
                """SELECT * FROM audio_metrics
                   WHERE sampled_at >= datetime('now', 'localtime', ?)
                   ORDER BY sampled_at DESC
                   LIMIT ?""",
                (f"-{hours} hours", limit)
            )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"查询音频指标失败: {e}")
            return []


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    reader = DBReader()
    
    # 测试读取配置
    print("\n=== 测试配置读取 ===")
    all_configs = reader.get_all_configs()
    print(f"所有配置: {all_configs}")
    
    # 测试读取事件
    print("\n=== 测试事件查询 ===")
    events = reader.get_recent_events(hours=24)
    print(f"最近24小时事件数: {len(events)}")
    for event in events[:3]:
        print(f"  - {event['event_type']} ({event['severity']}) at {event['created']}")
    
    # 测试统计
    print("\n=== 测试统计查询 ===")
    count = reader.get_event_count_today()
    print(f"今日事件总数: {count}")
    
    reader.close()
    print("\n测试完成")
