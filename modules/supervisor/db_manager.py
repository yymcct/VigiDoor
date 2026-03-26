"""
DBManager - 集中写入层

运行在 Supervisor 进程内的独立线程，是数据库写入的唯一入口。
所有子进程通过消息队列发送写入请求，DBManager 序列化执行。

核心职责：
1. 接收来自消息队列的写入请求
2. 序列化执行所有数据库写入操作
3. 定期清理过期数据
4. 处理写入异常和重试
"""

import sqlite3
import queue
import threading
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


class DBManager:
    """
    数据库管理器 - 集中写入层
    
    在 Supervisor 进程内作为独立线程运行
    """
    
    # 数据库文件目录
    DB_DIR = Path(__file__).parent.parent.parent / "data"
    
    # 数据保留期限 (天)
    RETENTION_DAYS = {
        "events": 7,           # 事件日志保留7天
        "arm_disarm_log": 180,  # 布撤防记录保留90天
        "metrics": 30,         # 统计数据保留30天
        "health_metrics": 7    # 健康指标保留7天
    }
    
    def __init__(self, write_queue: queue.Queue):
        """
        初始化 DBManager
        
        Args:
            write_queue: 写入请求队列
        """
        self.write_queue = write_queue
        self._connections: Dict[str, sqlite3.Connection] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
        # 确保数据库目录存在
        self.DB_DIR.mkdir(parents=True, exist_ok=True)
    
    def _connect(self, db_name: str) -> sqlite3.Connection:
        """
        连接到指定数据库
        
        Args:
            db_name: 数据库名称 (config/events/metrics)
            
        Returns:
            数据库连接对象
        """
        db_path = self.DB_DIR / f"{db_name}.db"
        logger.info(f"连接数据库: {db_path}")
        
        conn = sqlite3.connect(str(db_path), timeout=5)
        
        # 配置 WAL 模式和性能参数
        conn.execute("PRAGMA journal_mode=WAL")       # 读写独立
        conn.execute("PRAGMA synchronous=NORMAL")     # WAL下安全
        conn.execute("PRAGMA busy_timeout=3000")      # 忙等3秒
        
        return conn
    
    def _init_databases(self) -> None:
        """初始化所有数据库连接"""
        try:
            # 导入初始化函数
            from db.init_db import init_databases
            
            # 确保数据库文件和表结构存在
            init_databases(self.DB_DIR)
            
            # 建立连接
            for db_name in ["config", "events", "metrics"]:
                self._connections[db_name] = self._connect(db_name)
            
            logger.info("数据库连接初始化完成")
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")
            raise
    
    def start(self) -> None:
        """启动 DBManager 线程"""
        if self._running:
            logger.warning("DBManager 已经在运行")
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="DBManager")
        self._thread.start()
        logger.info("DBManager 线程已启动")
    
    def stop(self) -> None:
        """停止 DBManager 线程"""
        if not self._running:
            return
        
        logger.info("正在停止 DBManager...")
        self._running = False
        
        if self._thread:
            self._thread.join(timeout=5)
        
        logger.info("DBManager 已停止")
    
    def _run_loop(self) -> None:
        """主循环 - 处理写入请求"""
        logger.info("DBManager 主循环开始")
        
        # 在线程内初始化数据库连接（避免跨线程问题）
        try:
            self._init_databases()
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")
            return
        
        try:
            while self._running:
                try:
                    # 从队列获取写入请求 (超时1秒)
                    msg = self.write_queue.get(timeout=1.0)
                    self._dispatch_write(msg)
                except queue.Empty:
                    continue
                except Exception as e:
                    logger.error(f"DBManager 处理消息失败: {e}", exc_info=True)
        finally:
            # 在线程结束时关闭所有连接
            for conn in self._connections.values():
                try:
                    conn.close()
                except Exception as e:
                    logger.error(f"关闭数据库连接失败: {e}")
            logger.debug("所有数据库连接已关闭")
    
    def _dispatch_write(self, msg: Dict[str, Any]) -> None:
        """
        分发写入请求到对应的处理方法
        
        Args:
            msg: 写入请求消息
        """
        action = msg.get("action")
        
        try:
            if action == "write_event":
                self._write_event(msg["data"])
            elif action == "write_arm_disarm":
                self._write_arm_disarm(msg["data"])
            elif action == "write_metric":
                self._write_metric(msg["data"])
            elif action == "write_health_metric":
                self._write_health_metric(msg["data"])
            elif action == "set_config":
                self._set_config(msg["key"], msg["value"])
            elif action == "write_recording_start":
                self._write_recording_start(msg["data"])
            elif action == "finalize_recording_clip":
                self._finalize_recording_clip(msg["data"])
            elif action == "tag_clip_alarm":
                self._tag_clip_alarm(msg["data"])
            elif action == "cleanup":
                self._cleanup()
            else:
                logger.warning(f"未知的写入动作: {action}")
        except Exception as e:
            logger.error(f"执行写入动作失败 [{action}]: {e}", exc_info=True)
    
    def _write_event(self, data: Dict[str, Any]) -> None:
        """
        写入事件日志
        
        Args:
            data: 事件数据
                - event_type: 事件类型
                - severity: 严重程度 (low/medium/high)
                - source: 来源 (detector/audio)
                - confidence: 置信度
                - detail: 详细信息 (JSON字符串)
        """
        try:
            conn = self._connections["events"]
            conn.execute(
                """INSERT INTO events
                   (event_type, severity, source, confidence, detail)
                   VALUES (:event_type, :severity, :source, :confidence, :detail)""",
                data
            )
            conn.commit()
            logger.debug(f"事件已写入: {data.get('event_type')}")
        except Exception as e:
            logger.error(f"写入事件失败: {e}", exc_info=True)
    
    def _write_arm_disarm(self, data: Dict[str, Any]) -> None:
        """
        写入布撤防操作记录

        Args:
            data: 记录数据
                - action: 'arm' / 'disarm'
                - source: 触发来源 (mqtt/local/api 等)
                - operator: 操作者（可选）
                - ts: Unix 时间戳
        """
        try:
            conn = self._connections["events"]
            conn.execute(
                """INSERT INTO arm_disarm_log (action, source, operator, ts)
                   VALUES (:action, :source, :operator, :ts)""",
                {
                    "action": data["action"],
                    "source": data["source"],
                    "operator": data.get("operator"),
                    "ts": data["ts"],
                }
            )
            conn.commit()
            logger.info(f"布撤防记录已写入: {data.get('action')} (来源: {data.get('source')})")
        except Exception as e:
            logger.error(f"写入布撤防记录失败: {e}", exc_info=True)

    # ==================== 录像片段索引 ====================

    def _write_recording_start(self, data: Dict[str, Any]) -> None:
        """插入新录像片段行（片段开始时调用）"""
        try:
            conn = self._connections["events"]
            conn.execute(
                """INSERT OR IGNORE INTO recording_clips (file_path, start_time)
                   VALUES (:file_path, :start_time)""",
                data,
            )
            conn.commit()
            logger.debug(f"录像片段已记录: {data.get('file_path')}")
        except Exception as e:
            logger.error(f"写入录像片段失败: {e}", exc_info=True)

    def _finalize_recording_clip(self, data: Dict[str, Any]) -> None:
        """更新录像片段的结束时间、时长和文件大小（片段写完时调用）"""
        try:
            conn = self._connections["events"]
            file_path = data["file_path"]
            end_time = data["end_time"]
            file_size_bytes = data.get("file_size_bytes")

            row = conn.execute(
                "SELECT start_time FROM recording_clips WHERE file_path = ?",
                (file_path,),
            ).fetchone()

            duration = (end_time - row[0]) if row else None

            conn.execute(
                """UPDATE recording_clips
                   SET end_time = :end_time,
                       duration_seconds = :duration,
                       file_size_bytes = :file_size_bytes
                   WHERE file_path = :file_path""",
                {
                    "end_time": end_time,
                    "duration": duration,
                    "file_size_bytes": file_size_bytes,
                    "file_path": file_path,
                },
            )
            conn.commit()
            if duration:
                logger.debug(f"录像片段已完成: {file_path} ({duration:.1f}s)")
            else:
                logger.debug(f"录像片段已完成: {file_path}")
        except Exception as e:
            logger.error(f"更新录像片段失败: {e}", exc_info=True)

    def _tag_clip_alarm(self, data: Dict[str, Any]) -> None:
        """为录像片段打上报警标签（有 AI 事件时调用）"""
        try:
            conn = self._connections["events"]
            conn.execute(
                """UPDATE recording_clips
                   SET has_ai_event = 1,
                       alarm_level  = :alarm_level
                   WHERE file_path  = :file_path
                     AND alarm_level != 'alarm'""",
                data,
            )
            conn.commit()
            logger.info(f"录像片段已打标: {data.get('file_path')} → {data.get('alarm_level')}")
        except Exception as e:
            logger.error(f"打标录像片段失败: {e}", exc_info=True)

    def _write_metric(self, data: Dict[str, Any]) -> None:
        """
        写入统计数据 (预留)

        Args:
            data: 统计数据
        """
        # TODO: 实现统计数据写入逻辑
        logger.debug(f"写入统计数据: {data}")
    
    def _write_health_metric(self, data: Dict[str, Any]) -> None:
        """
        写入系统健康指标
        
        Args:
            data: 健康指标数据
                - timestamp: 采集时间戳
                - cpu_usage: CPU使用率
                - memory_usage: 内存使用率
                - disk_usage: 磁盘使用率
                - temperature: CPU温度
                - uptime: 系统运行时间
        """
        try:
            conn = self._connections["metrics"]
            conn.execute(
                """INSERT INTO health_metrics
                   (timestamp, cpu_usage, memory_usage, disk_usage, temperature, uptime)
                   VALUES (:timestamp, :cpu_usage, :memory_usage, :disk_usage, :temperature, :uptime)""",
                data
            )
            conn.commit()
            logger.debug(f"健康指标已写入: CPU={data.get('cpu_usage')}%, MEM={data.get('memory_usage')}%")
        except Exception as e:
            logger.error(f"写入健康指标失败: {e}", exc_info=True)
    
    def _set_config(self, key: str, value: str) -> None:
        """
        设置配置项
        
        Args:
            key: 配置键 (点号分隔的层级，如 "audio.volume_threshold_db")
            value: 配置值
        """
        try:
            conn = self._connections["config"]
            conn.execute(
                "INSERT OR REPLACE INTO kv_config (key, value) VALUES (?, ?)",
                (key, value)
            )
            conn.commit()
            logger.info(f"配置已更新: {key} = {value}")
        except Exception as e:
            logger.error(f"更新配置失败: {e}", exc_info=True)
    
    def _cleanup(self) -> None:
        """
        定期清理过期数据
        
        删除超过保留期限的旧数据，并执行 VACUUM 回收空间
        建议每天凌晨执行一次
        """
        logger.info("开始清理过期数据...")
        
        try:
            now = datetime.now()
            
            # 清理事件日志
            events_cutoff = now - timedelta(days=self.RETENTION_DAYS["events"])
            conn_events = self._connections["events"]
            
            cursor = conn_events.execute(
                "DELETE FROM events WHERE created < ?",
                (events_cutoff,)
            )
            deleted_events = cursor.rowcount
            conn_events.commit()
            
            logger.info(f"已删除 {deleted_events} 条过期事件")

            # 清理布撤防记录
            arm_cutoff = now - timedelta(days=self.RETENTION_DAYS["arm_disarm_log"])
            cursor = conn_events.execute(
                "DELETE FROM arm_disarm_log WHERE created < ?",
                (arm_cutoff,)
            )
            deleted_arm = cursor.rowcount
            conn_events.commit()
            logger.info(f"已删除 {deleted_arm} 条过期布撤防记录")

            # 清理统计数据 (预留)
            metrics_cutoff = now - timedelta(days=self.RETENTION_DAYS["metrics"])
            conn_metrics = self._connections["metrics"]
            
            cursor = conn_metrics.execute(
                "DELETE FROM people_count WHERE window_start < ?",
                (metrics_cutoff,)
            )
            deleted_metrics = cursor.rowcount
            conn_metrics.commit()
            
            logger.info(f"已删除 {deleted_metrics} 条过期统计")
            
            # 清理健康指标
            health_cutoff = now - timedelta(days=self.RETENTION_DAYS["health_metrics"])
            cursor = conn_metrics.execute(
                "DELETE FROM health_metrics WHERE recorded_at < ?",
                (health_cutoff,)
            )
            deleted_health = cursor.rowcount
            conn_metrics.commit()
            
            logger.info(f"已删除 {deleted_health} 条过期健康指标")
            
            # 执行 VACUUM 回收空间
            if deleted_events > 0 or deleted_arm > 0:
                conn_events.execute("VACUUM")
                logger.info("events.db VACUUM 完成")
            
            if deleted_metrics > 0:
                conn_metrics.execute("VACUUM")
                logger.info("metrics.db VACUUM 完成")
            
            logger.info("过期数据清理完成")
        except Exception as e:
            logger.error(f"清理数据失败: {e}", exc_info=True)
    
    def schedule_cleanup(self) -> None:
        """
        调度定期清理任务
        
        在后台线程中每24小时执行一次清理
        """
        def cleanup_task():
            import time
            while self._running:
                time.sleep(86400)  # 24小时
                if self._running:
                    self._cleanup()
        
        cleanup_thread = threading.Thread(target=cleanup_task, daemon=True, name="DBCleanup")
        cleanup_thread.start()
        logger.info("定期清理任务已启动 (每24小时)")


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 创建测试队列
    test_queue = queue.Queue()
    
    # 创建 DBManager
    manager = DBManager(test_queue)
    manager.start()
    
    # 测试写入事件
    test_queue.put({
        "action": "write_event",
        "data": {
            "event_type": "intrusion",
            "severity": "high",
            "source": "detector",
            "confidence": 0.92,
            "detail": '{"bbox": [0.3, 0.4, 0.2, 0.5]}'
        }
    })
    
    # 测试更新配置
    test_queue.put({
        "action": "set_config",
        "key": "audio.volume_threshold_db",
        "value": "55.0"
    })
    
    # 等待处理
    import time
    time.sleep(2)
    
    # 停止
    manager.stop()
    print("测试完成")
