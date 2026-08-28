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
from agent_runtime.task_store import InMemoryTaskStore, TaskStore
from flare_common.tenant import get_tenant_id
from model_gateway.mock import MockModelProvider
from tools_gateway.builtin import create_default_registry
from tools_gateway.registry import ToolRegistry

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
    tenant_id: str = "default"  # M5：多租户隔离边界

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
            "tenant_id": self.tenant_id,
        }


class TaskManager:
    """进程内任务管理（L1：后台执行 + 实时流）。"""

    def __init__(
        self,
        *,
        registry=None,
        llm=None,
        checkpointer_factory=None,
        memory=None,
        store=None,
    ) -> None:
        self._registry = registry or create_default_registry()
        self._llm = llm or MockModelProvider()
        self._checkpointer_factory = checkpointer_factory or get_checkpointer
        self._memory = memory  # M3b 分层记忆（None 则不做上下文注入）
        self._store: TaskStore = store or InMemoryTaskStore()  # M5：持久化存储
        self._tasks: dict[str, TaskRecord] = {}  # 进程内缓存（同步读 + 持久化写穿）

    @property
    def registry(self) -> ToolRegistry:
        """F1.4：供多 Agent 子任务运行时共享同一工具注册表。"""
        return self._registry

    @property
    def llm(self):
        """F1.4：供多 Agent 子任务运行时共享同一模型入口。"""
        return self._llm

    async def create(
        self,
        task_input: str,
        *,
        thread_id: str | None = None,
        max_steps: int = 5,
        tenant_id: str | None = None,
    ) -> TaskRecord:
        """登记任务并后台执行，立即返回（L1：请求不被任务耗时阻塞）。"""
        task = TaskRecord(
            task_id=uuid.uuid4().hex[:12],
            thread_id=thread_id or uuid.uuid4().hex[:12],
            task_input=task_input,
            max_steps=max_steps,
            tenant_id=tenant_id or get_tenant_id(),
        )
        self._tasks[task.task_id] = task
        await self._store.create(task)
        asyncio.create_task(self._execute(task))
        return task

    async def _recent_messages(self, checkpointer, thread_id: str, limit: int = 6) -> list[str]:
        """M1：取该线程已持久化的近期对话（user/assistant），供短期对话层注入。

        续聊（同一 thread 复用）时才有历史；新线程返回空列表。
        checkpointer.aget 对无快照线程返回 None，防御性兜底。
        """
        try:
            snapshot = await checkpointer.aget({"configurable": {"thread_id": thread_id}})
        except Exception:  # noqa: BLE001 - 不同 saver 实现的 aget 行为差异，防御兜底
            return []
        if snapshot is None:
            return []
        # MemorySaver 的 checkpoint 用 channel_values 存状态值（dict）；saver 实现差异大，做防御
        values = None
        if isinstance(snapshot, dict):
            values = snapshot.get("channel_values") or snapshot.get("values")
        else:
            values = getattr(snapshot, "values", None)
        if not values:
            return []
        msgs = values.get("messages") or []
        rows = [
            f"{m.role}: {m.content}"
            for m in msgs
            if getattr(m, "role", None) in ("user", "assistant")
        ]
        return rows[-limit:]

    async def _execute(self, task: TaskRecord) -> None:
        task.status = "running"
        await self._save(task)
        try:
            checkpointer = await self._checkpointer_factory()
            memory_context = None
            if self._memory is not None:
                # M1（F4.3）：任务开始时按 task_input 召回向量记忆 + 相关长期事实，
                # 并把该线程的近期对话取出传入 recent——三层记忆真正参与上下文工程
                recent = await self._recent_messages(checkpointer, task.thread_id)
                memory_context = await self._memory.build_context(
                    query=task.task_input, recent=recent
                )
            agent = build_react_agent(
                self._llm,
                self._registry,
                max_steps=task.max_steps,
                checkpointer=checkpointer,
                memory_context=memory_context,
            )
            async for update in agent.astream(
                {"task_input": task.task_input},
                {"configurable": {"thread_id": task.thread_id}},
                stream_mode="updates",
            ):
                task.events.append({"type": "step", "node": list(update.keys()), "data": update})
                await self._save(task)
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
        finally:
            await self._save(task)

    async def _save(self, task: TaskRecord) -> None:
        """写穿持久化 + 更新进程内缓存（M5：多实例/重启可恢复的底座）。

        仅当任务仍被登记时更新缓存：避免后台协程把已删除的任务"复活"回内存。
        """
        if task.task_id in self._tasks:
            self._tasks[task.task_id] = task
        await self._store.save(task)

    async def stream(self, task: TaskRecord) -> AsyncIterator[str]:
        """轮询 events 实时推送；终态后补 result 并结束。多客户端各自带索引，互不干扰。

        M5：每轮从 store 读取最新记录（InMemory 返回同一对象；SQLite/Redis 重新加载），
        保证持久化存储下也能正确流式。
        """
        idx = 0
        while True:
            cur = await self._store.get(task.task_id) or task
            if idx < len(cur.events):
                ev = cur.events[idx]
                idx += 1
                yield (
                    "event: step\n"
                    f"data: {json.dumps(ev, ensure_ascii=False, default=_json_default)}\n\n"
                )
                continue
            if cur.done:
                break
            await asyncio.sleep(0.05)
        payload = json.dumps(
            {"result": cur.result, "status": cur.status, "error": cur.error},
            ensure_ascii=False,
            default=_json_default,
        )
        yield "event: result\n" f"data: {payload}\n\n"

    async def close(self) -> None:
        """关闭持有的资源（M4/M5：模型 HTTP 客户端、任务存储连接等）。无实现自动跳过。"""
        close = getattr(self._llm, "close", None)
        if close is not None:
            await close()
        await self._store.close()

    def get(self, task_id: str) -> TaskRecord | None:
        return self._tasks.get(task_id)

    async def delete(self, task_id: str) -> bool:
        """删除任务（会话管理）。运行中的任务仅从存储移除，后台协程照常收尾。"""
        removed = self._tasks.pop(task_id, None) is not None
        if removed:
            await self._store.delete(task_id)
        return removed

    def recent(self, limit: int = 200) -> list[TaskRecord]:
        recs = sorted(self._tasks.values(), key=lambda t: t.created_at, reverse=True)
        return recs[:limit]
