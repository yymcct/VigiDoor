"""
数据库初始化脚本

创建三个数据库文件并初始化表结构：
- config.db: 配置信息 (key-value + 设备信息)
- events.db: 事件日志
- metrics.db: 统计数据 (预留)
"""

import sqlite3
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# TODO 检查没有db文件，直接新建db文件
class DatabaseInitializer:
    """数据库初始化器"""
    
    def __init__(self, db_dir: Path):
        """
        初始化数据库目录
        
        Args:
            db_dir: 数据库文件存放目录
        """
        self.db_dir = db_dir
        self.db_dir.mkdir(parents=True, exist_ok=True)
    
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
                    updated  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 创建设备信息表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS device_info (
                    device_id    TEXT PRIMARY KEY,
                    location     TEXT,
                    firmware_ver TEXT,
                    registered   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
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
                    created     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
            
            # 创建索引
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_people_window 
                ON people_count(window_start)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audio_sampled 
                ON audio_metrics(sampled_at)
            """)
            
            conn.commit()
            logger.info("统计数据库初始化完成")
        finally:
            conn.close()
    
    def init_all(self) -> None:
        """初始化所有数据库"""
        try:
            self.init_config_db()
            self.init_events_db()
            self.init_metrics_db()
            logger.info("所有数据库初始化成功")
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


if __name__ == "__main__":
    # 直接运行此脚本可初始化数据库
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    init_databases()
