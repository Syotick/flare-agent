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

from langgraph.types import Command

from agent_runtime.approval import ApprovalManager
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
    status: str = (
        "pending"  # pending | running | awaiting_approval | completed | budget_exceeded | failed
    )
    created_at: float = field(default_factory=time.time)
    events: list[dict] = field(default_factory=list)
    result: dict[str, Any] | None = None
    error: str | None = None
    tenant_id: str = "default"  # M5：多租户隔离边界
    workspace_id: str = "default"  # DSH 对齐：工作区（会话命名空间，Web 先选工作区再新建对话）

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
            "workspace_id": self.workspace_id,
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
        approval: ApprovalManager | None = None,
    ) -> None:
        self._registry = registry or create_default_registry()
        self._llm = llm or MockModelProvider()
        self._checkpointer_factory = checkpointer_factory or get_checkpointer
        self._memory = memory  # M3b 分层记忆（None 则不做上下文注入）
        self._store: TaskStore = store or InMemoryTaskStore()  # M5：持久化存储
        self._approval = approval  # F1.3 审批管理器（None=不启用审批门）
        self._tasks: dict[str, TaskRecord] = {}  # 进程内缓存（同步读 + 持久化写穿）

    @property
    def registry(self) -> ToolRegistry:
        """F1.4：供多 Agent 子任务运行时共享同一工具注册表。"""
        return self._registry

    @property
    def llm(self):
        """F1.4：供多 Agent 子任务运行时共享同一模型入口。"""
        return self._llm

    def set_llm(self, llm) -> Any:
        """模型设置：热替换模型入口（对新建任务生效；正在运行的任务不受影响）。

        返回旧实例，调用方负责 await 其 close() 释放 HTTP 客户端等资源。
        """
        old = self._llm
        self._llm = llm
        return old

    @property
    def approval(self) -> ApprovalManager | None:
        """F1.3：审批管理器（供审批路由/测试读取；None=未启用审批门）。"""
        return self._approval

    async def create(
        self,
        task_input: str,
        *,
        thread_id: str | None = None,
        max_steps: int = 5,
        tenant_id: str | None = None,
        workspace_id: str | None = None,
    ) -> TaskRecord:
        """登记任务并后台执行，立即返回（L1：请求不被任务耗时阻塞）。"""
        task = TaskRecord(
            task_id=uuid.uuid4().hex[:12],
            thread_id=thread_id or uuid.uuid4().hex[:12],
            task_input=task_input,
            max_steps=max_steps,
            tenant_id=tenant_id or get_tenant_id(),
            workspace_id=workspace_id or "default",
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
            # F1.3/F2.4：审批门 + TOFU 作用域（thread=会话线程 / tenant=租户 / off=关闭）
            approval_scope = None
            if self._approval is not None:
                approval_scope = self._approval.scope_for(task.thread_id, task.tenant_id)
            agent = build_react_agent(
                self._llm,
                self._registry,
                max_steps=task.max_steps,
                checkpointer=checkpointer,
                memory_context=memory_context,
                approval=self._approval,  # F1.3：None=不启用审批门
                approval_scope=approval_scope,  # TOFU：已信任的工具免 interrupt 直行
                # L6：LLM 每吐一段 token 实时写入 events → SSE stream 轮询即时推前端（打字机）
                on_token=lambda d: task.events.append({"type": "token", "content": d}),
            )
            # F1.3 中断恢复循环：工具需审批时图发 interrupt 挂起 → 登记审批请求 +
            # 状态转 awaiting_approval → 等人工决策（REST）→ Command(resume=...) 续跑。
            pending_input: Any = {"task_input": task.task_input}
            while True:
                interrupted = False
                async for update in agent.astream(
                    pending_input,
                    {"configurable": {"thread_id": task.thread_id}},
                    stream_mode="updates",
                ):
                    if "__interrupt__" in update:
                        for intr in update["__interrupt__"]:
                            payload = intr.value
                            if (
                                self._approval is not None
                                and isinstance(payload, dict)
                                and payload.get("type") == "approval"
                            ):
                                req = await self._approval.register(
                                    task.task_id,
                                    payload["tool"],
                                    payload.get("args") or {},
                                    permission=payload.get("permission", "destructive"),
                                    description=payload.get("description", ""),
                                    scope=approval_scope,
                                )
                                task.events.append(
                                    {
                                        "type": "approval",
                                        "node": ["tool_executor"],
                                        "data": {"approval": req.to_dict()},
                                    }
                                )
                                task.status = "awaiting_approval"
                                await self._save(task)
                                decision = await self._approval.wait(req.approval_id)
                                task.events.append(
                                    {
                                        "type": "approval_decision",
                                        "node": [],
                                        "data": {"approval": req.to_dict()},
                                    }
                                )
                                task.status = "running"
                                await self._save(task)
                                pending_input = Command(
                                    resume={
                                        "approved": decision["approved"],
                                        "reason": decision["reason"],
                                    }
                                )
                            else:
                                pending_input = Command(resume=None)
                        interrupted = True
                        break
                    task.events.append(
                        {"type": "step", "node": list(update.keys()), "data": update}
                    )
                    await self._save(task)
                if not interrupted:
                    break
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

    async def get(self, task_id: str) -> TaskRecord | None:
        """查询任务：先查进程内缓存（热路径），miss 则回退持久 store（重启后可恢复历史）。"""
        task = self._tasks.get(task_id)
        if task is not None:
            return task
        return await self._store.get(task_id)

    async def delete(self, task_id: str) -> bool:
        """删除任务（会话管理）。运行中的任务仅从存储移除，后台协程照常收尾。

        直接删缓存 + 持久 store（不依赖缓存命中——重启后从 store 恢复的历史任务
        同样可删，而不是因缓存 miss 而静默失败）。
        """
        self._tasks.pop(task_id, None)
        return await self._store.delete(task_id)

    async def recent(self, limit: int = 200, workspace: str | None = None) -> list[TaskRecord]:
        """最近任务列表（从持久 store 读——sqlite/redis 下重启后可恢复历史会话）。

        workspace 非空时只返回该工作区的会话（Web 先选工作区再区分对话）。
        """
        recs = await self._store.list(limit)
        recs.sort(key=lambda t: t.created_at, reverse=True)
        if workspace:
            recs = [t for t in recs if t.workspace_id == workspace]
        return recs[:limit]

    async def workspaces(self, limit: int = 200) -> list[dict]:
        """聚合工作区列表（含默认）：id + 会话数 + 最近使用时间。

        基于持久化 store.list()（重启后可聚合历史会话）；进程内缓存可能缺失
        重启前的任务，store 是唯一权威来源。结果按最近使用倒序。
        """
        counts: dict[str, int] = {}
        last: dict[str, float] = {}
        for t in await self._store.list(limit):
            ws = t.workspace_id or "default"
            counts[ws] = counts.get(ws, 0) + 1
            last[ws] = max(last.get(ws, 0.0), t.created_at)
        # 始终包含默认工作区（用户可能一个会话都没建）
        for ws in set(counts) | {"default"}:
            last.setdefault(ws, 0.0)
        rows = [
            {"workspace_id": ws, "task_count": counts.get(ws, 0), "last_used_at": last[ws]}
            for ws in set(counts) | {"default"}
        ]
        rows.sort(key=lambda r: r["last_used_at"], reverse=True)
        return rows
