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
from flare_common.errors import FlareError

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
    # M5：生产接 PostgreSQL AsyncPostgresSaver（同库承载 checkpoints 表）
    _saver_cache = await _create_pg_saver(settings.database_url)
    return _saver_cache


class CheckpointUnavailableError(FlareError):
    """生产 checkpoint 依赖缺失/连不上 PG -> fail-fast（绝不静默降级）。"""

    code = "CHECKPOINT_UNAVAILABLE"
    status_code = 503


async def _create_pg_saver(dsn: str):
    """创建长生命周期 AsyncPostgresSaver（守卫式）：缺依赖/连不上 -> CheckpointUnavailableError。

    注意：from_conn_string 是 async 上下文管理器（退出即断连），
    进程级单例需自建 asyncpg 长连接传给构造函数。
    """
    try:
        import asyncpg
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    except ImportError as exc:  # noqa: PERF203 - 仅生产路径触发
        raise CheckpointUnavailableError(
            f"生产环境需安装 asyncpg 与 langgraph-checkpoint-postgres：{exc}"
        ) from exc
    try:
        conn = await asyncpg.connect(dsn)
        saver = AsyncPostgresSaver(conn=conn)
        await saver.setup()
    except Exception as exc:  # noqa: BLE001 - 连接失败统一转可用性错误
        raise CheckpointUnavailableError(f"无法连接 PostgreSQL checkpointer: {exc}") from exc
    return saver
