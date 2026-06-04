"""
日志配置 (loguru).

策略
----
- 默认输出到 stdout (Docker/K8s 友好, 由容器层收集)
- 文件日志由 FileRotationConfig 控制大小/保留 (开发用)
- 拦截标准 logging (uvicorn/sqlalchemy/httpx 等都接管)
- 彩色输出仅在 TTY (生产环境会自动禁用)

调用
----
    from backend.core.logging import logger
    logger.info("hello {}", "world")
"""
from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

from loguru import logger as _loguru_logger

if TYPE_CHECKING:
    from backend.core.config import Settings


# ============================================
# 拦截标准 logging
# ============================================
class _InterceptHandler(logging.Handler):
    """把标准 logging 记录重定向到 loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = _loguru_logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame.f_back and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        _loguru_logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logging(settings: "Settings") -> None:
    """初始化日志. 启动时调用一次即可."""
    import os

    from pathlib import Path

    log_settings = settings.log
    app_settings = settings.app

    # 1) 清除默认 sink
    _loguru_logger.remove()

    # 2) stdout sink (带色彩, 容器内禁用色彩)
    isatty = sys.stdout.isatty() and "PYCHARM_HOSTED" not in os.environ
    _loguru_logger.add(
        sys.stdout,
        level=log_settings.level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        )
        if isatty
        else "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
        backtrace=True,
        diagnose=False,
        enqueue=True,  # 进程安全
    )

    # 3) 文件 sink (开发环境, 生产可注释)
    if app_settings.env == "development":
        log_dir = Path("./logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        _loguru_logger.add(
            log_dir / "app.log",
            level=log_settings.level,
            rotation=log_settings.rotation,
            retention=log_settings.retention,
            encoding="utf-8",
            enqueue=True,
            backtrace=True,
            diagnose=False,
        )

    # 4) 拦截标准 logging
    logging.basicConfig(handlers=[_InterceptHandler()], level=0)
    for noisy in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi", "sqlalchemy.engine", "httpx"):
        logging.getLogger(noisy).handlers = [_InterceptHandler()]
        logging.getLogger(noisy).propagate = False

    _loguru_logger.info("📝 日志初始化完成 | level={} | env={}", log_settings.level, app_settings.env)


# 业务代码统一从此导入
logger = _loguru_logger
