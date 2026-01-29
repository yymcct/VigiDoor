"""
共享内存帧缓冲
实现三缓冲区机制，用于进程间高效传递视频帧
"""

import struct
import time
from multiprocessing import shared_memory
import numpy as np
from utils.logger import setup_logger

logger = setup_logger('frame_buffer')


class SharedFrameBuffer:
    """
    三缓冲帧共享内存
    
    内存布局:
    [Header | Buffer0 | Buffer1 | Buffer2]
    
    Header (64 bytes):
      - write_index: 当前写入缓冲区索引 (4 bytes)
      - frame_id: 帧序号 (8 bytes)
      - timestamp: 时间戳 (8 bytes)
      - width, height: 分辨率 (4+4 bytes)
      - format: 像素格式 (4 bytes, 0=RGB, 1=YUV)
      - fps: 当前帧率 (4 bytes)
      - reserved: 保留字段 (32 bytes)
    
    BufferN (width*height*3 bytes):
      - RGB888原始像素数据
    """
    
    BUFFER_COUNT = 3
    HEADER_FORMAT = '<IQdIIII8I'  # write_idx, frame_id, timestamp, w, h, fmt, fps, reserved(8个int)
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
    
    def __init__(self, width=1280, height=720, name="vigidoor_frames", create=False):
        """
        初始化共享内存帧缓冲
        
        Args:
            width: 帧宽度
            height: 帧高度
            name: 共享内存名称
            create: 是否创建新的共享内存（True=写入者，False=读取者）
        """
        self.width = width
        self.height = height
        self.frame_size = width * height * 3  # RGB
        self.name = name
        
        # 计算总大小
        self.total_size = self.HEADER_SIZE + self.frame_size * self.BUFFER_COUNT
        
        # 创建/打开共享内存
        try:
            if create:
                # 写入者：创建共享内存
                self.shm = shared_memory.SharedMemory(
                    name=name, 
                    create=True, 
                    size=self.total_size
                )
                logger.info(f"✅ 创建共享内存: {name} ({self._format_size(self.total_size)})")
                
                # 初始化header
                self._init_header()
            else:
                # 读取者：打开已存在的共享内存
                self.shm = shared_memory.SharedMemory(name=name)
                logger.info(f"✅ 打开共享内存: {name}")
                
        except FileExistsError:
            logger.warning(f"共享内存 {name} 已存在，尝试重新打开")
            # 如果已存在但要求创建，先关闭再重新创建
            try:
                old_shm = shared_memory.SharedMemory(name=name)
                old_shm.close()
                old_shm.unlink()
                logger.info(f"已清理旧共享内存: {name}")
            except:
                pass
            
            # 重新创建
            self.shm = shared_memory.SharedMemory(
                name=name, 
                create=True, 
                size=self.total_size
            )
            self._init_header()
        
        # 映射header为字节数组
        self.header_bytes = self.shm.buf[:self.HEADER_SIZE]
        
        # 映射三个缓冲区为NumPy数组
        self.buffers = []
        for i in range(self.BUFFER_COUNT):
            offset = self.HEADER_SIZE + i * self.frame_size
            buf = np.ndarray(
                (height, width, 3),
                dtype=np.uint8,
                buffer=self.shm.buf[offset:offset+self.frame_size]
            )
            self.buffers.append(buf)
    
    def _init_header(self):
        """初始化header数据"""
        header_data = struct.pack(
            self.HEADER_FORMAT,
            0,              # write_index
            0,              # frame_id
            0.0,            # timestamp
            self.width,     # width
            self.height,    # height
            0,              # format (0=RGB)
            0,              # fps
            0, 0, 0, 0, 0, 0, 0, 0  # reserved (8个int)
        )
        self.shm.buf[:self.HEADER_SIZE] = header_data
    
    def write_frame(self, frame, frame_id=None, timestamp=None):
        """
        写入新帧（无锁设计）
        
        Args:
            frame: NumPy数组 (height, width, 3) uint8
            frame_id: 帧序号（可选，自动递增）
            timestamp: 时间戳（可选，自动生成）
        """
        # 验证帧尺寸
        if frame.shape != (self.height, self.width, 3):
            raise ValueError(
                f"帧尺寸不匹配: 期望{(self.height, self.width, 3)}, "
                f"实际{frame.shape}"
            )
        
        # 读取当前header
        header_values = self._read_header()
        current_write_idx, current_frame_id = header_values[0], header_values[1]
        
        # 选择下一个缓冲区
        next_write_idx = (current_write_idx + 1) % self.BUFFER_COUNT
        
        # 生成frame_id和timestamp
        if frame_id is None:
            frame_id = current_frame_id + 1
        if timestamp is None:
            timestamp = time.time()
        
        # 复制帧数据到共享内存
        np.copyto(self.buffers[next_write_idx], frame)
        
        # 原子更新header
        self._write_header(next_write_idx, frame_id, timestamp)
    
    def read_frame(self, copy=True):
        """
        读取最新完成的帧（无锁设计）
        
        Args:
            copy: 是否返回副本（推荐True，避免数据竞争）
        
        Returns:
            (frame, frame_id, timestamp) 或 None（如果无有效帧）
        """
        # 读取header
        header_values = self._read_header()
        write_idx, frame_id, timestamp = header_values[:3]
        
        # 检查是否有有效帧（frame_id > 0）
        if frame_id == 0:
            return None
        
        # 读取帧数据
        frame = self.buffers[write_idx]
        
        if copy:
            # 返回副本（避免数据竞争）
            return frame.copy(), frame_id, timestamp
        else:
            # 直接返回（高性能，但需注意数据竞争）
            return frame, frame_id, timestamp
    
    def get_info(self):
        """获取当前缓冲区信息"""
        header_values = self._read_header()
        write_idx, frame_id, timestamp, width, height, fmt, fps = header_values[:7]
        
        return {
            'write_index': write_idx,
            'frame_id': frame_id,
            'timestamp': timestamp,
            'width': width,
            'height': height,
            'format': 'RGB' if fmt == 0 else 'YUV',
            'fps': fps,
            'age': time.time() - timestamp if timestamp > 0 else 0
        }
    
    def _read_header(self):
        """从header读取所有字段"""
        header_data = bytes(self.header_bytes)
        return struct.unpack(self.HEADER_FORMAT, header_data)
    
    def _write_header(self, write_idx, frame_id, timestamp, fps=0):
        """原子更新header"""
        header_data = struct.pack(
            self.HEADER_FORMAT,
            write_idx,
            frame_id,
            timestamp,
            self.width,
            self.height,
            0,              # format (RGB)
            fps,
            0, 0, 0, 0, 0, 0, 0, 0  # reserved (8个int)
        )
        self.header_bytes[:] = header_data
    
    def cleanup(self):
        """清理共享内存（仅写入者调用）"""
        try:
            logger.info(f"🧹 清理共享内存: {self.name}")
            self._release_views()
            self.shm.close()
            self.shm.unlink()
        except Exception as e:
            logger.error(f"清理共享内存失败: {e}")
    
    def close(self):
        """关闭共享内存（读取者调用）"""
        try:
            self._release_views()
            self.shm.close()
            logger.info(f"关闭共享内存: {self.name}")
        except Exception as e:
            logger.error(f"关闭共享内存失败: {e}")

    def _release_views(self):
        """释放对共享内存的所有视图引用，避免 BufferError"""
        try:
            if hasattr(self, 'buffers') and self.buffers is not None:
                for i in range(len(self.buffers)):
                    self.buffers[i] = None
                self.buffers = None

            if hasattr(self, 'header_bytes'):
                self.header_bytes = None
        except Exception as e:
            logger.debug(f"释放共享内存视图失败: {e}")
    
    @staticmethod
    def _format_size(size_bytes):
        """格式化字节数"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} TB"
    
    def __del__(self):
        """析构函数"""
        try:
            if hasattr(self, 'shm'):
                self._release_views()
                self.shm.close()
        except:
            pass


class FramePool:
    """
    帧内存池 - 预分配帧缓冲，避免频繁内存分配
    """
    
    def __init__(self, count=10, shape=(720, 1280, 3)):
        """
        Args:
            count: 池大小
            shape: 帧形状 (height, width, channels)
        """
        self.shape = shape
        self.pool = [np.empty(shape, dtype=np.uint8) for _ in range(count)]
        self.available = list(range(count))
        logger.info(f"📦 帧内存池初始化: {count}个缓冲区, 形状={shape}")
    
    def acquire(self):
        """获取一个可用帧"""
        if self.available:
            idx = self.available.pop()
            return self.pool[idx]
        else:
            # 池耗尽，临时分配
            logger.warning("帧池耗尽，临时分配")
            return np.empty(self.shape, dtype=np.uint8)
    
    def release(self, frame):
        """释放帧回池中"""
        try:
            idx = self.pool.index(frame)
            if idx not in self.available:
                self.available.append(idx)
        except ValueError:
            # 不在池中的帧（临时分配的），直接丢弃
            pass
    
    def get_usage(self):
        """获取池使用情况"""
        total = len(self.pool)
        available = len(self.available)
        return {
            'total': total,
            'available': available,
            'in_use': total - available,
            'usage_percent': (total - available) / total * 100
        }
