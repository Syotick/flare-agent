"""结构化日志初始化。本地 dev 可读格式；生产可切换 JSON 格式。"""

from __future__ import annotations

import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    """配置全局日志。"""
    fmt = "%(asctime)s %(levelname)s %(name)s %(message)s"
    logging.basicConfig(level=level.upper(), stream=sys.stdout, format=fmt)
    # 减少框架噪音
    logging.getLogger("uvicorn.access").setLevel("WARNING")
    logging.getLogger("httpx").setLevel("WARNING")
