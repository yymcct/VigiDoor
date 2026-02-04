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
