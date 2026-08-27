"""任务服务层（M2-4c）：TaskManager 编排 agent 图执行，记录执行轨迹事件与结果。

单用户 dev 阶段：进程内存储；M5 迁移 Redis/DB（多实例 + 任务队列）。
checkpointer 走 get_checkpointer（SQLite 落盘），同一 thread_id 可跨请求续跑。
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from agent_runtime.checkpoint import get_checkpointer
from agent_runtime.graph import build_react_agent
from model_gateway.mock import MockModelProvider
from tools_gateway.builtin import create_default_registry


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


class TaskManager:
    """进程内任务管理（M2-4c）。"""

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

    async def create_and_run(
        self,
        task_input: str,
        *,
        thread_id: str | None = None,
        max_steps: int = 5,
    ) -> TaskRecord:
        """创建任务并同步跑到终态，记录执行轨迹。"""
        task = TaskRecord(
            task_id=uuid.uuid4().hex[:12],
            thread_id=thread_id or uuid.uuid4().hex[:12],
            task_input=task_input,
            max_steps=max_steps,
        )
        self._tasks[task.task_id] = task
        task.status = "running"

        checkpointer = await self._checkpointer_factory()
        agent = build_react_agent(
            self._llm, self._registry, max_steps=max_steps, checkpointer=checkpointer
        )
        try:
            async for update in agent.astream(
                {"task_input": task_input},
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
        except Exception as exc:  # noqa: BLE001 - 顶层兜底，任务标记失败而非崩请求
            task.status = "failed"
            task.error = str(exc)
        return task

    def get(self, task_id: str) -> TaskRecord | None:
        return self._tasks.get(task_id)

    def to_sse(self, task: TaskRecord) -> AsyncIterator[str]:
        """把任务轨迹转成 SSE 文本流（step 事件 + result 收尾）。"""
        for ev in task.events:
            yield f"event: {ev['type']}\ndata: {json.dumps(ev, ensure_ascii=False, default=_json_default)}\n\n"
        yield (
            "event: result\n"
            f"data: {json.dumps({'result': task.result, 'status': task.status, 'error': task.error}, ensure_ascii=False, default=_json_default)}\n\n"
        )
