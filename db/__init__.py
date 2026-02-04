"""
数据库模块 - SQLite 数据持久化

本模块提供 VigiDoor 系统的数据持久化能力，包括：
- 配置信息存储 (config.db)
- 事件日志记录 (events.db)
- 统计数据预留 (metrics.db)

设计原则：
- 写入集中 (DBManager 在 Supervisor 进程)
- 读取分层 (L1缓存/L2本地连接/L3进程缓存)
- WAL模式 (多进程并发读安全)
"""

__version__ = "1.0.0"
__all__ = ["DBReader", "CachedDBReader", "DBWriterHelper", "init_databases"]

from .reader import DBReader
from .cached_reader import CachedDBReader
from .writer_helper import DBWriterHelper
from .init_db import init_databases
