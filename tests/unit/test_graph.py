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

    async def chat(self, messages, *, model=None, temperature=None, max_tokens=None) -> LLMResponse:
        content = json.dumps(
            {"action": "call_tool", "tool": {"name": "echo", "args": {"text": "x"}}}
        )
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


async def test_checkpoint_isolates_threads() -> None:
    agent = build_react_agent(
        MockModelProvider(), create_default_registry(), checkpointer=MemorySaver()
    )
    r1 = await agent.ainvoke({"task_input": "a"}, {"configurable": {"thread_id": "thread-a"}})
    r2 = await agent.ainvoke({"task_input": "b"}, {"configurable": {"thread_id": "thread-b"}})
    assert "echo: a" in r1["output"]
    assert "echo: b" in r2["output"]
