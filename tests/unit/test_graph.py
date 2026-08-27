"""LangGraph ReAct 核心循环测试。"""

from __future__ import annotations

import json

from langgraph.checkpoint.memory import MemorySaver

from agent_runtime.graph import build_react_agent
from model_gateway.mock import MockModelProvider
from model_gateway.providers import LLMResponse, LLMUsage
from tools_gateway.builtin import create_default_registry


class AlwaysToolProvider:
    """测试桩：一直要求调用工具（验证预算熔断）。"""

    model = "always-tool"

    async def chat(
        self, messages, *, model=None, temperature=None, max_tokens=None, tools=None
    ) -> LLMResponse:
        content = json.dumps(
            {"action": "call_tool", "tool": {"name": "echo", "args": {"text": "x"}}}
        )
        return LLMResponse(content=content, model=self.model, usage=LLMUsage())

    async def stream(self, messages, *, model=None, temperature=None):
        resp = await self.chat(messages, model=model, temperature=temperature)
        yield resp.content


class FixedDecisionProvider:
    """固定决策序列的测试桩：队列用完后按最后一次观察收尾。"""

    model = "fixed"

    def __init__(self, decisions: list[dict]) -> None:
        self._queue = list(decisions)

    async def chat(
        self, messages, *, model=None, temperature=None, max_tokens=None, tools=None
    ) -> LLMResponse:
        if self._queue:
            content = json.dumps(self._queue.pop(0))
        else:
            content = json.dumps({"action": "final", "answer": f"完成: {messages[-1].content}"})
        return LLMResponse(content=content, model=self.model, usage=LLMUsage())

    async def stream(self, messages, *, model=None, temperature=None):
        resp = await self.chat(messages, model=model, temperature=temperature)
        yield resp.content


async def test_react_loop_completes_with_tool() -> None:
    agent = build_react_agent(
        MockModelProvider(), create_default_registry(), checkpointer=MemorySaver()
    )
    result = await agent.ainvoke({"task_input": "hello"}, {"configurable": {"thread_id": "t1"}})
    assert result["status"] == "completed"
    assert "echo: hello" in result["output"]
    assert result["step_count"] == 1


async def test_budget_guard_stops_runaway() -> None:
    agent = build_react_agent(
        AlwaysToolProvider(), create_default_registry(), max_steps=2, checkpointer=MemorySaver()
    )
    result = await agent.ainvoke({"task_input": "x"}, {"configurable": {"thread_id": "t2"}})
    assert result["status"] == "budget_exceeded"
    assert result["step_count"] == 2


async def test_tool_then_final_with_min_budget() -> None:
    """F2: max_steps=1 时，最后一次工具观察必须还能让模型收尾（修复 off-by-one）。"""
    agent = build_react_agent(
        MockModelProvider(), create_default_registry(), max_steps=1, checkpointer=MemorySaver()
    )
    result = await agent.ainvoke({"task_input": "hi"}, {"configurable": {"thread_id": "t-min"}})
    assert result["status"] == "completed"
    assert "echo: hi" in result["output"]


async def test_unknown_tool_is_observed_not_crash() -> None:
    """F1: 模型调用未知工具 → 结构化失败观察回灌，任务不崩、模型可重试。"""
    provider = FixedDecisionProvider(
        [{"action": "call_tool", "tool": {"name": "no_such_tool", "args": {}}}]
    )
    agent = build_react_agent(provider, create_default_registry(), checkpointer=MemorySaver())
    result = await agent.ainvoke({"task_input": "x"}, {"configurable": {"thread_id": "t-unknown"}})
    assert result["status"] == "completed"
    joined = "\n".join(m.content for m in result["messages"])
    assert "UNKNOWN_TOOL" in joined
    assert "no_such_tool" in joined


async def test_invalid_args_is_observed_not_crash() -> None:
    """F1: 模型参数非法 → INVALID_ARGS 观察回灌，任务不崩。"""
    provider = FixedDecisionProvider(
        [{"action": "call_tool", "tool": {"name": "echo", "args": {}}}]
    )
    agent = build_react_agent(provider, create_default_registry(), checkpointer=MemorySaver())
    result = await agent.ainvoke({"task_input": "x"}, {"configurable": {"thread_id": "t-invalid"}})
    assert result["status"] == "completed"
    joined = "\n".join(m.content for m in result["messages"])
    assert "INVALID_ARGS" in joined


async def test_invalid_model_output_is_observed() -> None:
    """F3: 模型输出非 JSON（坏决策）→ 显式 INVALID_MODEL_OUTPUT 观察，不静默当答案。"""
    provider = FixedDecisionProvider(["这不是 JSON"])
    agent = build_react_agent(provider, create_default_registry(), checkpointer=MemorySaver())
    result = await agent.ainvoke({"task_input": "x"}, {"configurable": {"thread_id": "t-badout"}})
    assert result["status"] == "completed"
    joined = "\n".join(m.content for m in result["messages"])
    assert "INVALID_MODEL_OUTPUT" in joined


async def test_semibaked_call_tool_without_tool_observed() -> None:
    """F3: call_tool 决策缺 tool（半熟决策）→ 校验拦截 → INVALID_MODEL_OUTPUT 观察。"""
    provider = FixedDecisionProvider([{"action": "call_tool"}])
    agent = build_react_agent(provider, create_default_registry(), checkpointer=MemorySaver())
    result = await agent.ainvoke({"task_input": "x"}, {"configurable": {"thread_id": "t-semi"}})
    assert result["status"] == "completed"
    joined = "\n".join(m.content for m in result["messages"])
    assert "INVALID_MODEL_OUTPUT" in joined


async def test_checkpoint_isolates_threads() -> None:
    agent = build_react_agent(
        MockModelProvider(), create_default_registry(), checkpointer=MemorySaver()
    )
    r1 = await agent.ainvoke({"task_input": "a"}, {"configurable": {"thread_id": "thread-a"}})
    r2 = await agent.ainvoke({"task_input": "b"}, {"configurable": {"thread_id": "thread-b"}})
    assert "echo: a" in r1["output"]
    assert "echo: b" in r2["output"]
