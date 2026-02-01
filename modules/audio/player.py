"""
音频播放器
处理远程喊话音频的播放
"""

import shutil
import subprocess
import threading
from pathlib import Path
from queue import Queue, Empty
from typing import Optional
from utils.logger import setup_logger

logger = setup_logger('audio_player')


class AudioPlayer:
    """
    音频播放器
    
    功能：
    1. 异步播放队列，不阻塞主线程
    2. 支持多种音频格式（MP3、WAV、AAC、OGG）
    3. 自动查找系统播放器
    
    参数：
    - device: 音频输出设备（None 为默认设备）
    """
    
    def __init__(self, device: Optional[str] = None):
        self.device = device
        
        # 播放队列
        self.play_queue = Queue(maxsize=10)
        
        # 线程控制
        self.running = False
        self.thread = None
        
        # 查找系统播放器
        self.player_cmd = self._find_player()
        
        # 统计
        self.total_plays = 0
        self.failed_plays = 0
        
        logger.info(f"音频播放器初始化")
        if self.player_cmd:
            logger.info(f"  使用播放器: {self.player_cmd[0]}")
        else:
            logger.warning("  未找到可用播放器")
    
    def _find_player(self) -> Optional[list]:
        """查找系统中可用的播放器"""
        candidates = [
            ["ffplay", "-nodisp", "-autoexit", "-loglevel", "error"],
            ["mpg123", "-q"],
            ["cvlc", "--play-and-exit", "--quiet"],
            ["play", "-q"],
            ["aplay"],  # 仅支持 WAV
        ]
        
        for cmd in candidates:
            if shutil.which(cmd[0]):
                logger.info(f"找到播放器: {cmd[0]}")
                return cmd
        
        logger.warning("未找到可用播放器，请安装 ffmpeg/mpg123/vlc/sox")
        return None
    
    def start(self) -> bool:
        """启动播放线程"""
        if self.running:
            logger.warning("播放线程已在运行")
            return False
        
        if self.player_cmd is None:
            logger.error("无可用播放器")
            return False
        
        self.running = True
        self.thread = threading.Thread(
            target=self._play_loop,
            daemon=True,
            name="AudioPlayer"
        )
        self.thread.start()
        
        logger.info("✅ 音频播放线程已启动")
        return True
    
    def play(self, audio_path: str) -> bool:
        """
        异步播放音频（将任务放入队列）
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            是否成功加入队列
        """
        try:
            self.play_queue.put_nowait(audio_path)
            logger.info(f"🔊 音频已加入播放队列: {audio_path}")
            return True
        except:
            logger.warning("播放队列已满")
            return False
    
    def _play_loop(self):
        """播放线程主循环"""
        logger.info("播放线程运行中...")
        
        while self.running:
            try:
                # 从队列获取音频路径
                audio_path = self.play_queue.get(timeout=0.5)
                
                # 执行播放
                self._play_sync(audio_path)
                
            except Empty:
                continue
            except Exception as e:
                logger.error(f"播放循环异常: {e}", exc_info=True)
    
    def _play_sync(self, audio_path: str):
        """
        同步播放音频
        
        Args:
            audio_path: 音频文件路径
        """
        self.total_plays += 1
        
        try:
            # 解析路径
            resolved_path = self._resolve_path(audio_path)
            if resolved_path is None:
                self.failed_plays += 1
                return
            
            # 构建播放命令
            cmd = self.player_cmd + [str(resolved_path)]
            
            logger.info(f"🔊 播放音频: {resolved_path.name}")
            
            # 执行播放
            result = subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30  # 最长播放 30 秒
            )
            
            if result.returncode == 0:
                logger.info("✅ 播放完成")
            else:
                logger.warning(f"播放失败，返回码: {result.returncode}")
                self.failed_plays += 1
                
        except subprocess.TimeoutExpired:
            logger.warning("播放超时")
            self.failed_plays += 1
        except Exception as e:
            logger.error(f"播放失败: {e}")
            self.failed_plays += 1
    
    def _resolve_path(self, audio_path: str) -> Optional[Path]:
        """
        解析音频路径
        
        Args:
            audio_path: 原始路径
            
        Returns:
            解析后的 Path 对象或 None
        """
        if not audio_path:
            logger.error("音频路径为空")
            return None
        
        # 转换为 Path 对象
        path = Path(audio_path)
        
        # 如果是相对路径，相对于项目根目录解析
        if not path.is_absolute():
            project_root = Path(__file__).resolve().parents[2]
            path = project_root / path
        
        # 检查文件是否存在
        if not path.exists():
            logger.error(f"音频文件不存在: {path}")
            return None
        
        return path
    
    def stop(self):
        """停止播放线程"""
        if not self.running:
            return
        
        logger.info("正在停止音频播放...")
        self.running = False
        
        # 等待线程结束
        if self.thread:
            self.thread.join(timeout=2.0)
        
        logger.info("✅ 音频播放已停止")
    
    def get_statistics(self) -> dict:
        """获取播放统计信息"""
        success_rate = (self.total_plays - self.failed_plays) / max(self.total_plays, 1) * 100
        
        return {
            'total_plays': self.total_plays,
            'failed_plays': self.failed_plays,
            'success_rate': f"{success_rate:.1f}%",
            'queue_size': self.play_queue.qsize()
        }
