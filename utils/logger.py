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
    
    # 解析日志级别（优先环境变量，其次配置文件）
    resolved_level = level
    env_level = os.getenv("VIGIDOOR_LOG_LEVEL") or os.getenv("LOG_LEVEL")
    if env_level:
        resolved_level = env_level
    else:
        try:
            from utils.config.manager import ConfigManager

            config = ConfigManager.get_instance()
            if config.logging and config.logging.level:
                resolved_level = config.logging.level
        except Exception:
            pass

    level_value = getattr(logging, str(resolved_level).upper(), logging.INFO)

    # 解析日志格式（若配置中存在）
    log_format = '%(asctime)s [%(levelname)s] [%(name)s] %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    try:
        from utils.config.manager import ConfigManager

        config = ConfigManager.get_instance()
        if config.logging and config.logging.format:
            log_format = config.logging.format
    except Exception:
        pass

    # 创建 logger
    logger = logging.getLogger(name)
    logger.setLevel(level_value)
    
    # 避免重复添加 handler
    if logger.handlers:
        for handler in logger.handlers:
            handler.setLevel(level_value)
            handler.setFormatter(logging.Formatter(log_format, datefmt=date_format))
        return logger
    
    # 文件 handler（带日志轮转）
    log_file = os.path.join(log_dir, f"{name}.log")
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(level_value)
    
    # 控制台 handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level_value)
    
    # 格式化器
    formatter = logging.Formatter(log_format, datefmt=date_format)
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # 添加 handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger
