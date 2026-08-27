"""Checkpoint 存储测试（F4）。"""

from __future__ import annotations

import pytest

from agent_runtime.checkpoint import _create_sqlite_saver, get_checkpointer
from agent_runtime.graph import build_react_agent
from model_gateway.mock import MockModelProvider
from tools_gateway.builtin import create_default_registry


async def test_sqlite_checkpoint_persists_across_savers(tmp_path) -> None:
    """F4: SQLite 写入后，新 saver 连接同一文件可恢复状态（真持久化冒烟）。"""
    db = tmp_path / "cp.sqlite3"
    saver1 = await _create_sqlite_saver(db)
    agent1 = build_react_agent(MockModelProvider(), create_default_registry(), checkpointer=saver1)
    r1 = await agent1.ainvoke({"task_input": "persist"}, {"configurable": {"thread_id": "th"}})
    assert r1["status"] == "completed"
    await saver1.conn.close()

    saver2 = await _create_sqlite_saver(db)
    agent2 = build_react_agent(MockModelProvider(), create_default_registry(), checkpointer=saver2)
    snap = await agent2.aget_state({"configurable": {"thread_id": "th"}})
    messages = snap.values.get("messages", [])
    assert any(m.content == "persist" for m in messages)
    await saver2.conn.close()


async def test_non_dev_env_fails_fast(monkeypatch) -> None:
    """F4（M5）：生产接 AsyncPostgresSaver；无 PG 可连 → CheckpointUnavailableError fail-fast。"""
    from agent_runtime.checkpoint import CheckpointUnavailableError
    from flare_common.config import Settings

    monkeypatch.setattr("agent_runtime.checkpoint.get_settings", lambda: Settings(env="prod"))
    with pytest.raises(CheckpointUnavailableError):
        await get_checkpointer()
