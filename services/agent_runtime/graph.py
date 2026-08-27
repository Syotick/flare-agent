"""LangGraph Agent 图（M2-4b：ReAct 核心循环）。

五节点计划：planner → actor ↔ tool_executor → reflect → finalize。
本步实现 ReAct 核心：actor(思考+决策) ↔ tool_executor(执行+观察)，含预算熔断。
LangGraph 图显式化循环的好处：每步可 checkpoint、可中断、可观测（对比裸 ReAct）。
"""

from __future__ import annotations

import json
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from model_gateway.providers import LLMMessage, ModelProvider
from tools_gateway.registry import ToolRegistry, ToolResult


class AgentState(TypedDict, total=False):
    task_input: str
    messages: list[LLMMessage]
    step_count: int
    pending_tool: dict[str, Any]  # {"name": str, "args": dict}
    action: str  # call_tool | final
    last_tool_result: ToolResult
    output: str
    status: str  # completed | budget_exceeded


def _tool_message(name: str, content: str) -> LLMMessage:
    return LLMMessage(role="tool", content=f"[{name}] {content}")


def _parse_decision(content: str) -> dict[str, Any]:
    """解析模型决策：JSON 工具调用（与 function-calling 同形态）；解析失败按最终回答。"""
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return {"action": "final", "answer": content}
    if data.get("action") == "call_tool" and isinstance(data.get("tool"), dict):
        tool = data["tool"]
        return {
            "action": "call_tool",
            "tool": {"name": str(tool.get("name", "")), "args": tool.get("args", {})},
        }
    return {"action": "final", "answer": data.get("answer", content)}


def build_react_agent(
    llm: ModelProvider,
    registry: ToolRegistry,
    *,
    max_steps: int = 5,
    checkpointer: Any = None,
):
    """构建 ReAct 核心图：actor ↔ tool_executor（带预算熔断）。

    - llm: ModelProvider 接口（多模型可路由的入口）
    - registry: ToolRegistry（工具执行）
    - checkpointer: LangGraph 持久化（SQLite/PG/内存）
    """

    async def actor(state: AgentState) -> dict[str, Any]:
        step = state.get("step_count", 0)
        if step >= max_steps:
            return {
                "output": f"已达预算上限(步骤数 {max_steps})，任务提前结束",
                "status": "budget_exceeded",
                "action": "final",
                "pending_tool": None,
            }
        messages = list(state.get("messages", []))
        if not messages:
            messages.append(LLMMessage(role="user", content=state.get("task_input", "")))
        response = await llm.chat(messages)
        messages.append(LLMMessage(role="assistant", content=response.content))
        decision = _parse_decision(response.content)
        if decision["action"] == "call_tool":
            return {"messages": messages, "pending_tool": decision["tool"], "action": "call_tool"}
        return {
            "messages": messages,
            "output": decision.get("answer", response.content),
            "status": "completed",
            "action": "final",
            "pending_tool": None,
        }

    async def tool_executor(state: AgentState) -> dict[str, Any]:
        tool = state.get("pending_tool")
        if tool is None:  # 防御：无待执行工具时原样返回
            return {}
        result = await registry.execute(tool["name"], tool.get("args"))
        return {
            "step_count": state.get("step_count", 0) + 1,
            "pending_tool": None,
            "last_tool_result": result,
            "messages": [*state.get("messages", []), _tool_message(tool["name"], result.content)],
        }

    def route_after_actor(state: AgentState) -> str:
        return "tool_executor" if state.get("action") == "call_tool" else "__end__"

    builder = StateGraph(AgentState)
    builder.add_node("actor", actor)
    builder.add_node("tool_executor", tool_executor)
    builder.add_edge(START, "actor")
    builder.add_conditional_edges(
        "actor",
        route_after_actor,
        {"tool_executor": "tool_executor", "__end__": END},
    )
    builder.add_edge("tool_executor", "actor")
    return builder.compile(checkpointer=checkpointer)
