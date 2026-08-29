"""多 Agent / Subagent 并行测试（F1.4）。

覆盖：单子任务执行、并行并发性（max_active>=2 证明 gather 真并发）、
超时护栏、spawn/await/list/run 工具流、错误路径、create_app 接线。
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator

import pytest

from agent_runtime.app import create_app
from agent_runtime.tasks import TaskManager
from flare_common.config import Settings
from model_gateway.mock import MockModelProvider
from model_gateway.providers import LLMResponse, ToolCall, ToolCallDecision
from subagent.runtime import SubagentRuntime
from subagent.sub_tools import build_subagent_tools
from tools_gateway.builtin import create_default_registry
from tools_gateway.registry import Tool, ToolRegistry, ToolResult


class _SlowProvider:
    """调 slow_tool 一次后收尾的确定性供应商（用于并发/超时测试）。"""

    model = "slow"

    async def chat(self, messages, *, model=None, temperature=None, max_tokens=None, tools=None):
        last = messages[-1] if messages else None
        if last is not None and last.role == "tool":
            answer = ToolCallDecision(action="final", answer=f"done: {last.content}")
        else:
            user = next((m.content for m in messages if m.role == "user"), "")
            answer = ToolCallDecision(
                action="call_tool", tool=ToolCall(name="slow_tool", args={"text": user})
            )
        return LLMResponse(content=answer.model_dump_json(), model="slow")

    async def stream(self, messages, *, model=None, temperature=None, tools: list[dict] | None = None) -> AsyncIterator[str]:
        resp = await self.chat(messages, model=model, temperature=temperature, tools=tools)
        yield resp.content


def _slow_registry(state: dict) -> ToolRegistry:
    registry = ToolRegistry()

    async def slow_tool(**kwargs: str) -> ToolResult:
        state["active"] += 1
        state["max_active"] = max(state["max_active"], state["active"])
        await asyncio.sleep(0.3)
        state["active"] -= 1
        return ToolResult(ok=True, content=f"slow: {kwargs['text']}")

    registry.register(
        Tool(
            name="slow_tool",
            description="d",
            parameters={"type": "object", "properties": {"text": {"type": "string"}}},
            func=slow_tool,
        )
    )
    return registry


async def test_single_subagent_completes():
    rt = SubagentRuntime(MockModelProvider(), create_default_registry())
    record = rt.spawn("你好")
    assert record.status == "pending"
    output = await rt.await_subagent(record.subagent_id)
    assert record.status == "completed", record.error
    assert "echo" in output  # mock 模型 echo 后收尾
    await rt.close()


async def test_parallel_run_subagents_is_concurrent():
    """F1.4 核心：3 个各睡 0.3s 的子任务并行，总耗时接近单个而非串行之和。"""
    state = {"active": 0, "max_active": 0}
    rt = SubagentRuntime(_SlowProvider(), _slow_registry(state), timeout=5.0)
    t0 = time.monotonic()
    results = await rt.run_subagents(["a", "b", "c"])
    dt = time.monotonic() - t0
    assert len(results) == 3
    assert all(r["status"] == "completed" for r in results), results
    assert state["max_active"] >= 2, f"应并发执行（max_active={state['max_active']}）"
    assert dt < 0.9, f"应并行而非串行（实际 {dt:.2f}s，串行约 0.9s+）"
    await rt.close()


async def test_subagent_timeout_marks_timed_out():
    state = {"active": 0, "max_active": 0}
    registry = _slow_registry(state)

    async def _long(**kwargs: str) -> ToolResult:
        await asyncio.sleep(2)  # 远超子任务超时 0.2s
        return ToolResult(ok=True, content="late")

    # 覆盖 slow_tool 为长睡版本，验证子任务超时护栏
    registry._tools["slow_tool"] = Tool(
        name="slow_tool",
        description="d",
        parameters={"type": "object", "properties": {"text": {"type": "string"}}},
        func=_long,
    )
    rt = SubagentRuntime(_SlowProvider(), registry, timeout=0.2)
    record = rt.spawn("x", timeout=0.2)
    await rt.await_subagent(record.subagent_id, timeout=2.0)
    assert record.status == "timed_out", record.status
    assert "超时" in (record.error or "")
    await rt.close()


async def test_subagent_budget_independent():
    # 每个子 Agent 独立 max_steps：小预算不拖累并行
    rt = SubagentRuntime(MockModelProvider(), create_default_registry(), max_steps=1)
    record = rt.spawn("hello", max_steps=1)
    await rt.await_subagent(record.subagent_id)
    assert record.status in ("completed", "budget_exceeded")
    await rt.close()


async def test_spawn_empty_prompt_raises():
    rt = SubagentRuntime(MockModelProvider(), create_default_registry())
    with pytest.raises(ValueError):
        rt.spawn("   ")
    await rt.close()


async def test_tools_spawn_await_list():
    registry = ToolRegistry()
    rt = SubagentRuntime(MockModelProvider(), registry)
    for tool in build_subagent_tools(rt):
        registry.register(tool)

    res = await registry.execute("spawn_subagent", {"prompt": "hi"})
    assert res.ok is True, res.content
    sid = rt.list()[-1].subagent_id
    res2 = await registry.execute("await_subagent", {"subagent_id": sid})
    assert res2.ok is True, res2.content
    assert "echo" in res2.content
    listed = await registry.execute("list_subagents", {})
    assert sid in listed.content
    await rt.close()


async def test_tools_run_subagents_parallel():
    registry = ToolRegistry()
    rt = SubagentRuntime(MockModelProvider(), registry)
    for tool in build_subagent_tools(rt):
        registry.register(tool)
    res = await registry.execute("run_subagents", {"prompts": ["a", "b"]})
    assert res.ok is True, res.content
    assert res.content.count("=== subagent") == 2
    assert res.content.count("[completed]") == 2
    await rt.close()


async def test_tools_error_paths():
    registry = ToolRegistry()
    rt = SubagentRuntime(MockModelProvider(), registry)
    for tool in build_subagent_tools(rt):
        registry.register(tool)

    bad = await registry.execute("spawn_subagent", {"prompt": ""})
    assert bad.ok is False and bad.error_code == "SUBAGENT_SPAWN_ERROR"
    missing = await registry.execute("await_subagent", {"subagent_id": "nope"})
    assert missing.ok is False and missing.error_code == "SUBAGENT_NOT_FOUND"
    empty = await registry.execute("run_subagents", {"prompts": []})
    assert empty.ok is False and empty.error_code == "INVALID_ARGS"
    too_many = await registry.execute("run_subagents", {"prompts": [str(i) for i in range(20)]})
    assert too_many.ok is False and too_many.error_code == "INVALID_ARGS"
    await rt.close()


def test_create_app_registers_subagent_tools():
    tm = TaskManager(registry=create_default_registry())
    create_app(settings=Settings(env="test"), task_manager=tm)
    names = [t.name for t in tm.registry.list()]
    for expected in ("spawn_subagent", "await_subagent", "list_subagents", "run_subagents"):
        assert expected in names, f"缺 {expected}"
