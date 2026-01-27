"""
日志配置工具
"""

import logging
import os
from logging.handlers import RotatingFileHandler


def setup_logger(name: str, log_dir: str = "./logs", level: str = "INFO") -> logging.Logger:
    """
    配置日志记录器
    
    Args:
        name: 日志记录器名称（通常是进程名）
        log_dir: 日志目录
        level: 日志级别
        
    Returns:
        配置好的 Logger 对象
    """
    # 创建日志目录
    os.makedirs(log_dir, exist_ok=True)
    
    # 创建 logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # 避免重复添加 handler
    if logger.handlers:
        return logger
    
    # 文件 handler（带日志轮转）
    log_file = os.path.join(log_dir, f"{name}.log")
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    
    # 控制台 handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # 格式化器
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # 添加 handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger
