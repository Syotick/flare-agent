"""任务服务层（M2-4c，Round3-L1 真·流式）：POST 立即返回，后台执行，SSE 实时推送。

- create(): 登记任务 + asyncio 后台执行，立即返回（不阻塞请求）
- stream(): 轮询 events + 终态判断——多客户端 / 刷新重连各自带索引，互不干扰
- 进程内存储（M5 迁移 Redis/DB）；checkpointer 走 get_checkpointer（SQLite 落盘）
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from agent_runtime.checkpoint import get_checkpointer
from agent_runtime.graph import build_react_agent
from model_gateway.mock import MockModelProvider
from tools_gateway.builtin import create_default_registry

logger = logging.getLogger(__name__)

TERMINAL = frozenset({"completed", "budget_exceeded", "failed"})


def _json_default(obj: Any) -> Any:
    """dataclass（LLMMessage/ToolResult 等）转 dict，供 SSE 事件序列化。"""
    if hasattr(obj, "__dataclass_fields__"):
        return {k: getattr(obj, k) for k in obj.__dataclass_fields__}
    raise TypeError(f"不可序列化: {type(obj)}")


@dataclass
class TaskRecord:
    task_id: str
    thread_id: str
    task_input: str
    max_steps: int
    status: str = "pending"  # pending | running | completed | budget_exceeded | failed
    created_at: float = field(default_factory=time.time)
    events: list[dict] = field(default_factory=list)
    result: dict[str, Any] | None = None
    error: str | None = None

    @property
    def done(self) -> bool:
        return self.status in TERMINAL

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "thread_id": self.thread_id,
            "task_input": self.task_input,
            "status": self.status,
            "created_at": self.created_at,
            "step_count": (self.result or {}).get("step_count", 0),
            "event_count": len(self.events),
            "result": self.result,
            "error": self.error,
        }


class TaskManager:
    """进程内任务管理（L1：后台执行 + 实时流）。"""

    def __init__(
        self,
        *,
        registry=None,
        llm=None,
        checkpointer_factory=None,
    ) -> None:
        self._registry = registry or create_default_registry()
        self._llm = llm or MockModelProvider()
        self._checkpointer_factory = checkpointer_factory or get_checkpointer
        self._tasks: dict[str, TaskRecord] = {}

    async def create(
        self,
        task_input: str,
        *,
        thread_id: str | None = None,
        max_steps: int = 5,
    ) -> TaskRecord:
        """登记任务并后台执行，立即返回（L1：请求不被任务耗时阻塞）。"""
        task = TaskRecord(
            task_id=uuid.uuid4().hex[:12],
            thread_id=thread_id or uuid.uuid4().hex[:12],
            task_input=task_input,
            max_steps=max_steps,
        )
        self._tasks[task.task_id] = task
        asyncio.create_task(self._execute(task))
        return task

    async def _execute(self, task: TaskRecord) -> None:
        task.status = "running"
        try:
            checkpointer = await self._checkpointer_factory()
            agent = build_react_agent(
                self._llm,
                self._registry,
                max_steps=task.max_steps,
                checkpointer=checkpointer,
            )
            async for update in agent.astream(
                {"task_input": task.task_input},
                {"configurable": {"thread_id": task.thread_id}},
                stream_mode="updates",
            ):
                task.events.append({"type": "step", "node": list(update.keys()), "data": update})
            final = await agent.aget_state({"configurable": {"thread_id": task.thread_id}})
            values = final.values
            task.result = {
                "status": values.get("status"),
                "output": values.get("output", ""),
                "step_count": values.get("step_count", 0),
                "message_count": len(values.get("messages", [])),
            }
            task.status = values.get("status", "failed")
        except Exception as exc:  # noqa: BLE001 - 顶层兜底：任务标记失败而非崩请求
            logger.exception("task %s failed: %s", task.task_id, exc)
            task.status = "failed"
            task.error = str(exc)

    async def stream(self, task: TaskRecord) -> AsyncIterator[str]:
        """轮询 events 实时推送；终态后补 result 并结束。多客户端各自带索引，互不干扰。"""
        idx = 0
        while True:
            if idx < len(task.events):
                ev = task.events[idx]
                idx += 1
                yield (
                    "event: step\n"
                    f"data: {json.dumps(ev, ensure_ascii=False, default=_json_default)}\n\n"
                )
                continue
            if task.done:
                break
            await asyncio.sleep(0.02)
        payload = json.dumps(
            {"result": task.result, "status": task.status, "error": task.error},
            ensure_ascii=False,
            default=_json_default,
        )
        yield "event: result\n" f"data: {payload}\n\n"

    def get(self, task_id: str) -> TaskRecord | None:
        return self._tasks.get(task_id)

    def delete(self, task_id: str) -> bool:
        """删除任务（会话管理）。运行中的任务仅从存储移除，后台协程照常收尾。"""
        return self._tasks.pop(task_id, None) is not None

    def recent(self, limit: int = 200) -> list[TaskRecord]:
        recs = sorted(self._tasks.values(), key=lambda t: t.created_at, reverse=True)
        return recs[:limit]
