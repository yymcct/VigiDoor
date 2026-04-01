"""
数据库初始化脚本

创建三个数据库文件并初始化表结构：
- config.db: 配置信息 (key-value + 设备信息)
- events.db: 事件日志
- metrics.db: 统计数据 (预留)
"""

import sqlite3
import json
import yaml
from pathlib import Path
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

class DatabaseInitializer:
    """数据库初始化器"""
    
    def __init__(self, db_dir: Path, config_path: Optional[Path] = None):
        """
        初始化数据库目录
        
        Args:
            db_dir: 数据库文件存放目录
            config_path: config.yaml 配置文件路径，默认为项目根目录下的 config.yaml
        """
        self.db_dir = db_dir
        self.db_dir.mkdir(parents=True, exist_ok=True)
        
        # 确定 config.yaml 路径
        if config_path is None:
            # 默认路径：项目根目录 / config.yaml
            config_path = Path(__file__).parent.parent / "config.yaml"
        self.config_path = config_path
    
    def _flatten_dict(self, data: Dict[Any, Any], parent_key: str = '', sep: str = '.') -> Dict[str, str]:
        """
        将嵌套字典扁平化为点分隔的 key-value 格式
        
        Args:
            data: 嵌套字典
            parent_key: 父级键名
            sep: 分隔符
            
        Returns:
            扁平化的字典，所有值转为 JSON 字符串
        """
        items = []
        for k, v in data.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            
            if isinstance(v, dict):
                # 递归处理嵌套字典
                items.extend(self._flatten_dict(v, new_key, sep=sep).items())
            else:
                # 字符串直接存储，其他类型转为 JSON 字符串（保留类型信息）
                if isinstance(v, str):
                    items.append((new_key, v))
                else:
                    items.append((new_key, json.dumps(v, ensure_ascii=False)))
        
        return dict(items)
    
    def _load_config(self) -> Dict[str, str]:
        """
        从 config.yaml 加载配置并扁平化
        
        Returns:
            扁平化的配置字典
        """
        if not self.config_path.exists():
            logger.warning(f"配置文件不存在: {self.config_path}")
            return {}
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            flattened = self._flatten_dict(config)
            logger.info(f"成功加载配置文件，共 {len(flattened)} 个配置项")
            return flattened
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            return {}
    
    def init_config_db(self) -> None:
        """初始化配置数据库"""
        db_path = self.db_dir / "config.db"
        logger.info(f"初始化配置数据库: {db_path}")
        
        conn = sqlite3.connect(str(db_path))
        try:
            # 启用 WAL 模式
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            
            # 创建 key-value 配置表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS kv_config (
                    key      TEXT PRIMARY KEY,
                    value    TEXT NOT NULL,
                    updated  TIMESTAMP DEFAULT (datetime('now','localtime'))
                )
            """)
            
            # 创建设备信息表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS device_info (
                    device_id    TEXT PRIMARY KEY,
                    location     TEXT,
                    firmware_ver TEXT,
                    registered   TIMESTAMP DEFAULT (datetime('now','localtime'))
                )
            """)
            
            # 从 config.yaml 加载初始配置
            config_data = self._load_config()
            if config_data:
                # 批量插入配置（使用 INSERT OR REPLACE 避免重复）
                cursor = conn.cursor()
                cursor.executemany(
                    "INSERT OR REPLACE INTO kv_config (key, value) VALUES (?, ?)",
                    config_data.items()
                )
                logger.info(f"已写入 {len(config_data)} 个配置项到 kv_config 表")
            
            conn.commit()
            logger.info("配置数据库初始化完成")
        finally:
            conn.close()
    
    def init_events_db(self) -> None:
        """初始化事件日志数据库"""
        db_path = self.db_dir / "events.db"
        logger.info(f"初始化事件数据库: {db_path}")
        
        conn = sqlite3.connect(str(db_path))
        try:
            # 启用 WAL 模式
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            
            # 创建事件表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type  TEXT NOT NULL,
                    severity    TEXT NOT NULL,
                    source      TEXT NOT NULL,
                    confidence  REAL,
                    detail      TEXT,
                    created     TIMESTAMP DEFAULT (datetime('now','localtime'))
                )
            """)
            
            # 创建索引
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_created 
                ON events(created)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_type 
                ON events(event_type)
            """)

            # 创建布撤防记录表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS arm_disarm_log (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    action    TEXT NOT NULL,
                    source    TEXT NOT NULL,
                    operator  TEXT,
                    ts        REAL NOT NULL,
                    created   TIMESTAMP DEFAULT (datetime('now','localtime'))
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_arm_disarm_ts
                ON arm_disarm_log(ts)
            """)

            # 创建录像片段索引表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS recording_clips (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path        TEXT NOT NULL UNIQUE,
                    start_time       REAL NOT NULL,
                    end_time         REAL,
                    duration_seconds REAL,
                    has_ai_event     INTEGER NOT NULL DEFAULT 0,
                    alarm_level      TEXT NOT NULL DEFAULT 'none'
                                         CHECK(alarm_level IN ('none', 'alert', 'alarm')),
                    file_size_bytes  INTEGER,
                    created_at       TIMESTAMP DEFAULT (datetime('now','localtime'))
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_clips_start_time
                ON recording_clips(start_time)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_clips_alarm_level
                ON recording_clips(alarm_level)
            """)

            conn.commit()
            logger.info("事件数据库初始化完成")
        finally:
            conn.close()
    
    def init_metrics_db(self) -> None:
        """初始化统计数据库 (预留)"""
        db_path = self.db_dir / "metrics.db"
        logger.info(f"初始化统计数据库: {db_path}")
        
        conn = sqlite3.connect(str(db_path))
        try:
            # 启用 WAL 模式
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            
            # 创建人流统计表 (预留)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS people_count (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    window_start TIMESTAMP NOT NULL,
                    window_end   TIMESTAMP NOT NULL,
                    count_in     INTEGER DEFAULT 0,
                    count_out    INTEGER DEFAULT 0,
                    count_peak   INTEGER DEFAULT 0
                )
            """)
            
            # 创建音频指标表 (预留)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audio_metrics (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    sampled_at  TIMESTAMP NOT NULL,
                    avg_db      REAL,
                    max_db      REAL,
                    event_count INTEGER DEFAULT 0
                )
            """)
            
            # 创建系统健康指标表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS health_metrics (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp     REAL NOT NULL,
                    cpu_usage     REAL,
                    memory_usage  REAL,
                    disk_usage    REAL,
                    temperature   REAL,
                    uptime        REAL,
                    recorded_at   TIMESTAMP DEFAULT (datetime('now','localtime'))
                )
            """)
            
            # 创建索引
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_people_window 
                ON people_count(window_start)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audio_sampled 
                ON audio_metrics(sampled_at)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_health_timestamp 
                ON health_metrics(timestamp)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_health_recorded 
                ON health_metrics(recorded_at)
            """)
            
            conn.commit()
            logger.info("统计数据库初始化完成")
        finally:
            conn.close()
    
    def init_all(self) -> None:
        """初始化所有数据库"""
        # 按需创建缺失的数据库文件：仅为不存在的数据库执行初始化操作
        config_db = self.db_dir / "config.db"
        events_db = self.db_dir / "events.db"
        metrics_db = self.db_dir / "metrics.db"

        created = []
        skipped = []

        try:
            if not config_db.exists():
                self.init_config_db()
                created.append("config.db")
            else:
                skipped.append("config.db")

            if not events_db.exists():
                self.init_events_db()
                created.append("events.db")
            else:
                skipped.append("events.db")

            if not metrics_db.exists():
                self.init_metrics_db()
                created.append("metrics.db")
            else:
                skipped.append("metrics.db")

            logger.info(f"数据库初始化完成；已创建: {created if created else '无'}；跳过: {skipped if skipped else '无'}")
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")
            raise


def init_databases(db_dir: Optional[Path] = None) -> None:
    """
    初始化所有数据库文件
    
    Args:
        db_dir: 数据库目录，默认为 ./data
    """
    if db_dir is None:
        db_dir = Path(__file__).parent.parent / "data"
    
    initializer = DatabaseInitializer(db_dir)
    initializer.init_all()


def ensure_migrations(db_dir: Optional[Path] = None) -> None:
    """
    幂等数据库迁移：确保所有新增表结构在已有数据库中存在

    用于系统升级时补全旧数据库缺少的表，可安全重复调用。

    Args:
        db_dir: 数据库目录，默认为 ./data
    """
    if db_dir is None:
        db_dir = Path(__file__).parent.parent / "data"

    events_db = db_dir / "events.db"
    if not events_db.exists():
        # events.db 不存在则跳过，init_all() 会在后续完整初始化
        return

    conn = sqlite3.connect(str(events_db))
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS arm_disarm_log (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                action    TEXT NOT NULL,
                source    TEXT NOT NULL,
                operator  TEXT,
                ts        REAL NOT NULL,
                created   TIMESTAMP DEFAULT (datetime('now','localtime'))
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_arm_disarm_ts
            ON arm_disarm_log(ts)
        """)

        # 录像片段索引表（migration 新增）
        conn.execute("""
            CREATE TABLE IF NOT EXISTS recording_clips (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path        TEXT NOT NULL UNIQUE,
                start_time       REAL NOT NULL,
                end_time         REAL,
                duration_seconds REAL,
                has_ai_event     INTEGER NOT NULL DEFAULT 0,
                alarm_level      TEXT NOT NULL DEFAULT 'none'
                                     CHECK(alarm_level IN ('none', 'alert', 'alarm')),
                file_size_bytes  INTEGER,
                created_at       TIMESTAMP DEFAULT (datetime('now','localtime'))
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_clips_start_time
            ON recording_clips(start_time)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_clips_alarm_level
            ON recording_clips(alarm_level)
        """)

        conn.commit()
        logger.info("数据库迁移完成：arm_disarm_log / recording_clips 表已就绪")
    except Exception as e:
        logger.error(f"数据库迁移失败: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    # 直接运行此脚本可初始化数据库
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    init_databases()
