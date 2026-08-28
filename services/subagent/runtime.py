"""多 Agent / Subagent 并行运行时（F1.4）。

设计：子任务 = 独立的 ReAct Agent 实例（复用 build_react_agent），
在进程内以 asyncio 后台任务并发执行；父 Agent 通过工具 spawn 一批 →
并行收集 → 自行汇总。这是 DSH/Codex 的"spawn 子 Agent"心智在本项目的落地。

关键决策：
- 子任务用 MemorySaver（进程内临时 checkpointer），结果以文本收集、不落任务存储
  （避开 dev SQLite checkpointer 长连接锁文件的坑；生产跨实例子任务随 M5 演进）
- 子 Agent 共享父的 llm 与工具注册表（可见全部工具，含再次 spawn——嵌套以数量/步数上限兜底）
- 预算独立：每个子 Agent 独立 max_steps，防单子任务无限跑
- 超时独立：await 支持 timeout，超时标记 timed_out 不拖垮父任务
- 并发护栏：存活子 Agent 数量上限 MAX_ACTIVE（防失控扇出）
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from langgraph.checkpoint.memory import MemorySaver

from agent_runtime.graph import build_react_agent
from flare_common.tenant import get_tenant_id
from model_gateway.providers import ModelProvider
from tools_gateway.registry import ToolRegistry

logger = logging.getLogger(__name__)

DEFAULT_MAX_STEPS = 3
DEFAULT_TIMEOUT = 30.0
MAX_ACTIVE = 64  # 并发/存活子 Agent 上限（防失控扇出）


@dataclass
class SubagentRecord:
    """一个子任务的生命周期记录（供 list/get/观测）。"""

    subagent_id: str
    prompt: str
    status: str = "pending"  # pending | running | completed | failed | timed_out
    output: str = ""
    error: str | None = None
    max_steps: int = DEFAULT_MAX_STEPS
    timeout: float = DEFAULT_TIMEOUT
    created_at: float = field(default_factory=time.time)
    step_count: int = 0
    tenant_id: str = "default"

    @property
    def done(self) -> bool:
        return self.status in ("completed", "failed", "timed_out")

    def to_dict(self) -> dict[str, Any]:
        return {
            "subagent_id": self.subagent_id,
            "prompt": self.prompt,
            "status": self.status,
            "output": self.output,
            "error": self.error,
            "max_steps": self.max_steps,
            "step_count": self.step_count,
            "created_at": self.created_at,
            "tenant_id": self.tenant_id,
        }


class SubagentRuntime:
    """子 Agent 运行时：spawn 独立 ReAct 循环 + 并行收集。"""

    def __init__(
        self,
        llm: ModelProvider,
        registry: ToolRegistry,
        *,
        max_steps: int = DEFAULT_MAX_STEPS,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._llm = llm
        self._registry = registry
        self._default_max_steps = max_steps
        self._default_timeout = timeout
        self._records: dict[str, SubagentRecord] = {}
        self._tasks: dict[str, asyncio.Task] = {}

    def _active_count(self) -> int:
        return sum(1 for r in self._records.values() if r.status in ("pending", "running"))

    def spawn(
        self,
        prompt: str,
        *,
        max_steps: int | None = None,
        timeout: float | None = None,
    ) -> SubagentRecord:
        """派生子任务：登记记录 + 后台启动独立 Agent 循环，立即返回。"""
        if not prompt or not str(prompt).strip():
            raise ValueError("子任务 prompt 不能为空")
        if self._active_count() >= MAX_ACTIVE:
            raise ValueError(f"子 Agent 数量已达上限 {MAX_ACTIVE}")
        record = SubagentRecord(
            subagent_id=uuid.uuid4().hex[:10],
            prompt=str(prompt),
            max_steps=max_steps or self._default_max_steps,
            timeout=timeout or self._default_timeout,
            tenant_id=get_tenant_id(),
        )
        self._records[record.subagent_id] = record
        self._tasks[record.subagent_id] = asyncio.create_task(self._run(record))
        return record

    async def _run(self, record: SubagentRecord) -> None:
        """运行一个子 Agent 的完整 ReAct 循环（独立图 + 独立预算/超时）。"""
        record.status = "running"
        try:
            # 子任务进程内临时，不落任务存储（避开 dev SQLite checkpointer 长连接锁文件坑）
            checkpointer = MemorySaver()
            agent = build_react_agent(
                self._llm,
                self._registry,
                max_steps=record.max_steps,
                checkpointer=checkpointer,
            )
            final = await asyncio.wait_for(
                agent.ainvoke(
                    {"task_input": record.prompt},
                    {"configurable": {"thread_id": record.subagent_id}},
                ),
                timeout=record.timeout,
            )
            record.status = str(final.get("status", "failed"))
            record.output = str(final.get("output", ""))
            record.step_count = int(final.get("step_count", 0))
            if record.status != "completed":
                record.error = record.output
        except TimeoutError:
            record.status = "timed_out"
            record.error = f"子任务超时（{record.timeout}s）"
        except Exception as exc:  # noqa: BLE001 - 子 Agent 失败不影响父任务
            logger.exception("subagent %s failed: %s", record.subagent_id, exc)
            record.status = "failed"
            record.error = str(exc)
        finally:
            self._tasks.pop(record.subagent_id, None)

    async def await_subagent(self, subagent_id: str, *, timeout: float | None = None) -> str:
        """等待一个子任务完成，返回其输出文本（超时标 timed_out，不取消底层任务）。"""
        record = self._records.get(subagent_id)
        if record is None:
            raise KeyError(f"未知子任务: {subagent_id}")
        task = self._tasks.get(subagent_id)
        if task is not None and not task.done():
            try:
                # shield：wait_for 超时只取消"等待"，不打断子 Agent 自身执行
                await asyncio.wait_for(asyncio.shield(task), timeout=timeout or record.timeout)
            except TimeoutError:
                record.status = "timed_out"
                record.error = f"等待子任务超时（{timeout or record.timeout}s）"
        return record.output

    async def run_subagents(
        self,
        prompts: list[str],
        *,
        max_steps: int | None = None,
        timeout: float | None = None,
    ) -> list[dict[str, Any]]:
        """F1.4 核心：spawn 一批子任务 + 并行收集（asyncio.gather）。

        所有子任务同时跑，全部完成后统一返回结果列表（父 Agent 自行汇总）。
        """
        if not prompts:
            return []
        records = [self.spawn(p, max_steps=max_steps, timeout=timeout) for p in prompts]
        ids = [r.subagent_id for r in records]
        if self._tasks:
            await asyncio.gather(*(self._tasks[i] for i in ids), return_exceptions=True)
        return [self._records[i].to_dict() for i in ids]

    def list(self) -> list[SubagentRecord]:
        return sorted(self._records.values(), key=lambda r: r.created_at)

    def get(self, subagent_id: str) -> SubagentRecord:
        return self._records[subagent_id]

    async def close(self) -> None:
        """取消所有仍在跑的子任务（父任务退出时清理）。"""
        pending = [t for t in self._tasks.values() if not t.done()]
        for t in pending:
            t.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        self._tasks.clear()
