"""
CachedDBReader - 带缓存的读取器 (L3层)

在进程内维护缓存，后台定期刷新。
适用于高频读取场景（如OSD显示人流数）。

特点：
- 主线程读取缓存（零延迟）
- 后台线程定期刷新
- 线程安全
"""

import threading
import time
import logging
from typing import Dict, Any, Optional

from .reader import DBReader

logger = logging.getLogger(__name__)


class CachedDBReader:
    """
    带缓存的数据库读取器
    
    后台刷新，前台读缓存，适合高频读取场景
    """
    
    def __init__(self, refresh_interval_sec: int = 5):
        """
        初始化缓存读取器
        
        Args:
            refresh_interval_sec: 缓存刷新间隔（秒）
        """
        self._reader = DBReader()
        self._cache: Dict[str, Any] = {}
        self._lock = threading.Lock()
        self._interval = refresh_interval_sec
        self._running = False
        self._thread: Optional[threading.Thread] = None
    
    def start(self) -> None:
        """启动后台刷新线程"""
        if self._running:
            logger.warning("CachedDBReader 已经在运行")
            return
        
        self._running = True
        self._thread = threading.Thread(
            target=self._refresh_loop,
            daemon=True,
            name="CachedDBReader"
        )
        self._thread.start()
        logger.info(f"CachedDBReader 已启动 (刷新间隔: {self._interval}秒)")
    
    def stop(self) -> None:
        """停止后台刷新线程"""
        if not self._running:
            return
        
        logger.info("正在停止 CachedDBReader...")
        self._running = False
        
        if self._thread:
            self._thread.join(timeout=5)
        
        self._reader.close()
        logger.info("CachedDBReader 已停止")
    
    def _refresh_loop(self) -> None:
        """后台刷新循环"""
        logger.info("CachedDBReader 刷新循环开始")
        
        while self._running:
            try:
                self._refresh_cache()
            except Exception as e:
                logger.error(f"缓存刷新失败: {e}", exc_info=True)
            
            # 等待下一次刷新
            for _ in range(self._interval):
                if not self._running:
                    break
                time.sleep(1)
    
    def _refresh_cache(self) -> None:
        """刷新缓存数据"""
        try:
            # 从数据库读取最新数据
            fresh_data = {
                # 人流统计（今天）
                "people_today": self._reader.get_people_stats(hours=24),
                
                # 事件数量（今天）
                "events_today": self._reader.get_event_count_today(),
                
                # 最近事件（最近1小时）
                "recent_events": self._reader.get_recent_events(hours=1, limit=10),
                
                # 高优先级事件（今天）
                "high_severity_events": self._reader.get_events_by_severity(
                    severity="high",
                    hours=24,
                    limit=10
                ),
            }
            
            # 原子更新缓存
            with self._lock:
                self._cache = fresh_data
            
            logger.debug("缓存已刷新")
        except Exception as e:
            logger.error(f"刷新缓存数据失败: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        从缓存读取数据（主线程调用）
        
        Args:
            key: 缓存键
            default: 默认值
            
        Returns:
            缓存的值，不存在时返回默认值
        """
        with self._lock:
            return self._cache.get(key, default)
    
    def get_all(self) -> Dict[str, Any]:
        """
        获取所有缓存数据
        
        Returns:
            缓存字典的副本
        """
        with self._lock:
            return self._cache.copy()
    
    # ==================== 便捷方法 ====================
    
    def get_people_count_today(self) -> Dict[str, int]:
        """
        获取今日人流统计
        
        Returns:
            {"total_in": 0, "total_out": 0, "peak": 0}
        """
        return self.get("people_today", {"total_in": 0, "total_out": 0, "peak": 0})
    
    def get_event_count_today(self) -> int:
        """
        获取今日事件总数
        
        Returns:
            事件数量
        """
        return self.get("events_today", 0)
    
    def get_recent_events(self, limit: int = 10) -> list:
        """
        获取最近事件
        
        Args:
            limit: 最大返回数量
            
        Returns:
            事件列表
        """
        events = self.get("recent_events", [])
        return events[:limit]
    
    def get_high_severity_events(self, limit: int = 10) -> list:
        """
        获取高优先级事件
        
        Args:
            limit: 最大返回数量
            
        Returns:
            事件列表
        """
        events = self.get("high_severity_events", [])
        return events[:limit]


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    reader = CachedDBReader(refresh_interval_sec=3)
    reader.start()
    
    print("\n=== 测试缓存读取 ===")
    
    # 等待首次刷新
    time.sleep(1)
    
    # 读取缓存数据
    for i in range(5):
        print(f"\n第 {i+1} 次读取:")
        print(f"  今日事件数: {reader.get_event_count_today()}")
        print(f"  今日人流: {reader.get_people_count_today()}")
        print(f"  最近事件数: {len(reader.get_recent_events())}")
        time.sleep(2)
    
    reader.stop()
    print("\n测试完成")
