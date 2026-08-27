"""Checkpoint 存储（长任务可恢复的底座）。

- 生产：PostgreSQL AsyncPostgresSaver（M5 上云，见 ADR-0001）
- 本地 dev：SQLite 降级（data/flare_agent.sqlite3，已 gitignore）
- 非 dev 且未接 Postgres：fail-fast 显式报错（F4），绝不静默回退内存假装"可恢复"
- 进程级单例缓存：checkpointer 生命周期与进程一致（首次 get_settings 钉死环境选择，属预期）
"""

from __future__ import annotations

import logging
from pathlib import Path

import aiosqlite
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from flare_common.config import get_settings

logger = logging.getLogger(__name__)

_sqlite_path = Path("data/flare_agent.sqlite3")

# F4: 进程级单例，避免反复新建连接导致泄漏
_saver_cache = None


async def _create_sqlite_saver(path: Path) -> AsyncSqliteSaver:
    """创建 SQLite saver（get_checkpointer 与测试共用）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(str(path))
    saver = AsyncSqliteSaver(conn)
    await saver.setup()
    return saver


async def get_checkpointer():
    """返回进程级 checkpointer（单例缓存；生产接 AsyncPostgresSaver）。"""
    global _saver_cache  # noqa: PLW0603
    if _saver_cache is not None:
        return _saver_cache
    settings = get_settings()
    if settings.env == "dev":
        try:
            _saver_cache = await _create_sqlite_saver(_sqlite_path)
            return _saver_cache
        except Exception as exc:  # noqa: BLE001 - 本地 SQLite 故障显式告警
            logger.warning("SQLite checkpoint 初始化失败，降级为内存（仅本次进程）: %s", exc)
            _saver_cache = MemorySaver()
            return _saver_cache
    raise NotImplementedError(
        "生产环境必须接入 Postgres checkpointer（AsyncPostgresSaver，M5）；"
        "当前无持久化实现，拒绝静默降级"
    )
