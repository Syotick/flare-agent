"""pytest 全局配置：测试环境隔离。

- FLARE_TASK_STORE=memory：测试默认不落盘（避免默认 sqlite 写 data/tasks.sqlite3
  污染真实数据 + 测试间串扰）。真实服务（uvicorn / make dev）仍用 sqlite 默认 → 会话持久。
"""

from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _isolate_task_store() -> None:
    os.environ["FLARE_TASK_STORE"] = "memory"
    yield
