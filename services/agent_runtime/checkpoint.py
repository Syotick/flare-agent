"""Checkpoint 存储（长任务可恢复的底座）。

生产：PostgreSQL AsyncPostgresSaver（M5 上云，见 ADR-0001）；
本地无 PG：SQLite 降级（data/flare_agent.sqlite3，已 gitignore）；
最坏回退：内存 MemorySaver（进程内，仅开发冒烟）。
"""

from __future__ import annotations

from pathlib import Path

import aiosqlite
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from flare_common.config import get_settings

_sqlite_path = Path("data/flare_agent.sqlite3")


async def get_checkpointer():
    """返回进程级 checkpointer（异步；随进程生命周期）。"""
    settings = get_settings()
    if settings.env == "dev":
        try:
            _sqlite_path.parent.mkdir(parents=True, exist_ok=True)
            conn = await aiosqlite.connect(str(_sqlite_path))
            saver = AsyncSqliteSaver(conn)
            await saver.setup()
            return saver
        except Exception:  # noqa: BLE001 - 本地 SQLite 不可用时降级
            return MemorySaver()
    return MemorySaver()  # 生产接 AsyncPostgresSaver（M5）
