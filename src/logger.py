"""结构化日志模块：控制台 + app.log + error.log。"""

import logging
import sys

from src.config import get_config

_LOG_FORMAT = "%(asctime)s | %(levelname)-5s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 全局文件 handlers（只初始化一次）
_file_handlers_initialized = False


def _init_file_handlers():
    global _file_handlers_initialized
    if _file_handlers_initialized:
        return

    log_dir = get_config("log_dir")
    log_dir.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(_LOG_FORMAT, _DATE_FORMAT)

    # app.log: 记录 DEBUG 及以上级别
    app_handler = logging.FileHandler(log_dir / "app.log", encoding="utf-8")
    app_handler.setLevel(logging.DEBUG)
    app_handler.setFormatter(formatter)

    # error.log: 仅记录 ERROR 及以上级别
    error_handler = logging.FileHandler(log_dir / "error.log", encoding="utf-8")
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)

    # 挂到 root logger，所有子 logger 都继承
    root = logging.getLogger()
    root.addHandler(app_handler)
    root.addHandler(error_handler)

    _file_handlers_initialized = True


def get_logger(name: str) -> logging.Logger:
    """获取带控制台 handler 的 logger（文件 handler 由 root logger 统一管理）。"""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, get_config("log_level").upper(), logging.INFO))
    logger.propagate = True  # 向上传递到 root logger，由 root 写入文件

    _add_console_handler(logger)
    _init_file_handlers()

    return logger


def _add_console_handler(logger: logging.Logger) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT, _DATE_FORMAT))
    logger.addHandler(handler)


default_logger = get_logger("app")
