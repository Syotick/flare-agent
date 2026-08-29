"""LangGraph Agent 图（M2-4b：ReAct 核心循环）。

五节点计划：planner → actor ↔ tool_executor → reflect → finalize。
本步实现 ReAct 核心：actor(思考+决策) ↔ tool_executor(执行+观察)，含预算熔断。
LangGraph 图显式化循环的好处：每步可 checkpoint、可中断、可观测（对比裸 ReAct）。
"""

from __future__ import annotations

import json
import logging
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from pydantic import ValidationError as PydanticValidationError

from agent_runtime.approval import ApprovalManager
from flare_common.errors import NotFoundError, ValidationError
from model_gateway.providers import LLMMessage, ModelProvider, ToolCallDecision
from tools_gateway.registry import ToolRegistry, ToolResult

logger = logging.getLogger(__name__)


class InvalidModelOutput(Exception):
    """模型输出无法解析为合法决策（F3：坏决策显式化，不静默吞掉）。"""


class AgentState(TypedDict, total=False):
    task_input: str
    messages: list[LLMMessage]
    step_count: int
    pending_tool: dict[str, Any]  # {"name": str, "args": dict}
    action: str  # call_tool | final
    last_tool_result: ToolResult
    output: str
    status: str  # completed | budget_exceeded


def _tool_message(name: str, result: ToolResult) -> LLMMessage:
    content = result.content
    if not result.ok and result.error_code:  # 失败观察带上错误码，模型才能知道发生了什么
        content = f"{result.error_code}: {content}"
    return LLMMessage(role="tool", content=f"[{name}] {content}")


def _build_tools_json(registry: ToolRegistry) -> list[dict]:
    """把工具注册表转成 OpenAI 原生 function-calling 工具清单（M4）。

    真实供应商（OpenAICompatibleProvider）用它做原生工具调用；
    mock / 文本型供应商忽略它（仍靠 system schema 提示）。两路并存，无感知切换。
    """
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            },
        }
        for t in registry.list()
    ]


def _build_tool_schema(registry: ToolRegistry) -> str:
    """把工具 schema（name/description/parameters）组装成 system 提示（R1）。

    真实模型必须"看得见"工具才会自主调用——只注册进 registry 不够，
    首轮必须把工具清单注入对话（system 消息），否则模型永远不知道有 kb_search/mem_recall。
    """
    lines = ["你是 Flare Agent，一个可调用工具完成任务的 AI。可用工具如下："]
    for tool in registry.list():
        lines.append(f"- {tool.name}: {tool.description}")
        lines.append(f"  参数(JSON Schema): {json.dumps(tool.parameters, ensure_ascii=False)}")
    lines.append("需要工具时按上述 schema 输出决策；否则直接回答。")
    return chr(10).join(lines)


def _parse_decision(content: str) -> ToolCallDecision:
    """解析模型决策为共享契约 ToolCallDecision（F3）。

    解析/校验失败抛 InvalidModelOutput，由 actor 显式记录并回灌观察，
    绝不把坏决策静默当答案（L3 fail-fast 哲学）。
    """
    try:
        return ToolCallDecision.model_validate(json.loads(content))
    except (json.JSONDecodeError, PydanticValidationError) as exc:
        raise InvalidModelOutput(f"模型输出无法解析为决策: {content[:200]!r}") from exc


def build_react_agent(
    llm: ModelProvider,
    registry: ToolRegistry,
    *,
    max_steps: int = 5,
    checkpointer: Any = None,
    memory_context: str | None = None,
    approval: ApprovalManager | None = None,
):
    """构建 ReAct 核心图：actor ↔ tool_executor（带预算熔断 + 审批门）。

    - llm: ModelProvider 接口（多模型可路由的入口）
    - registry: ToolRegistry（工具执行）
    - checkpointer: LangGraph 持久化（SQLite/PG/内存）
    - memory_context: M3b 分层记忆的上下文块，注入首个 user 消息（F4.3 上下文工程）
    - approval: F1.3 审批管理器（None=不启用审批门）。启用后，工具执行前若需审批
      （F2.4 权限分级），tool_executor 发 LangGraph interrupt 挂起任务，等人工决策：
      resume={"approved": True} 放行执行；False 拒绝并把拒绝观察回灌给模型。
    """

    async def actor(state: AgentState) -> dict[str, Any]:
        step = state.get("step_count", 0)
        # F2: step > max_steps —— 最后一次工具观察后，模型必须还有一次决策机会
        if step > max_steps:
            return {
                "output": f"已达预算上限(步骤数 {max_steps})，任务提前结束",
                "status": "budget_exceeded",
                "action": "final",
                "pending_tool": None,
            }
        messages = list(state.get("messages", []))
        task_input = state.get("task_input", "")
        # R1/M1-fix：每次 actor 进入都用当前 registry 重建 system 工具清单——
        # mcp_connect 中途注册的新工具（mcp__*）才能对模型可见，否则 function-calling
        # schema 冻结在首轮，同任务内新工具"假接线"（直接路径通、集成路径断）。
        # 保持仅一条 system 消息（原位替换，不污染历史）。
        sys_msg = LLMMessage(role="system", content=_build_tool_schema(registry))
        sys_idx = next((i for i, m in enumerate(messages) if m.role == "system"), None)
        if sys_idx is None:
            messages.append(sys_msg)
        else:
            messages[sys_idx] = sys_msg
        # M1：续聊（同一 thread 复用）时把本任务的输入作为新 user 消息追加；
        # 判定标准 = 是否已有以本任务输入结尾的 user 消息（同一任务内不会重复注入）
        already_injected = any(
            m.role == "user" and m.content.endswith(task_input) for m in messages
        )
        if not already_injected:
            content = task_input
            if memory_context:
                content = memory_context + "\n\n" + content
            messages.append(LLMMessage(role="user", content=content))
        tools = _build_tools_json(registry) if registry.list() else None
        response = await llm.chat(messages, tools=tools)
        messages.append(LLMMessage(role="assistant", content=response.content))
        try:
            decision = _parse_decision(response.content)
        except InvalidModelOutput as exc:
            # F3: 坏决策显式化——记日志 + 回灌 INVALID_MODEL_OUTPUT 观察，让模型重试
            logger.warning("INVALID_MODEL_OUTPUT: %s", exc)
            messages.append(LLMMessage(role="tool", content=f"INVALID_MODEL_OUTPUT: {exc}"))
            return {
                "messages": messages,
                "step_count": step + 1,
                "pending_tool": None,
                "action": "call_tool",
            }
        if decision.action == "call_tool" and decision.tool is not None:
            return {
                "messages": messages,
                "pending_tool": {"name": decision.tool.name, "args": decision.tool.args},
                "action": "call_tool",
            }
        return {
            "messages": messages,
            "output": decision.answer or response.content,
            "status": "completed",
            "action": "final",
            "pending_tool": None,
        }

    async def tool_executor(state: AgentState) -> dict[str, Any]:
        tool = state.get("pending_tool")
        if tool is None:  # 防御：无待执行工具时原样返回
            return {}
        # F2: 执行第 max_steps 次工具调用前拦截（模型坏决策不再触发第 max+1 次执行）
        step = state.get("step_count", 0)
        if step >= max_steps:
            return {
                "step_count": step,
                "output": f"已达预算上限(步骤数 {max_steps})，任务提前结束",
                "status": "budget_exceeded",
                "pending_tool": None,
                "action": "final",
            }
        name = tool["name"]
        args = tool.get("args") or {}
        # F1.3/F2.4 审批门：破坏性/策略要求的工具执行前 interrupt 挂起，等人工决策。
        # resume={"approved": True} 放行执行；False 拒绝，拒绝观察回灌给模型（agent 换路/收尾）。
        if approval is not None:
            try:
                tool_obj = registry.get(name)
                needs_approval = approval.requires_approval(tool_obj)
            except NotFoundError:
                needs_approval = False
            if needs_approval:
                resume = interrupt(
                    {
                        "type": "approval",
                        "tool": tool_obj.name,
                        "description": tool_obj.description,
                        "args": args,
                        "permission": tool_obj.permission,
                    }
                )
                if not resume.get("approved"):
                    reason = str(resume.get("reason", "")).strip()
                    msg = f"操作被拒绝：{reason}" if reason else "操作被用户拒绝"
                    rejected = ToolResult(ok=False, error_code="APPROVAL_REJECTED", content=msg)
                    return {
                        "step_count": step + 1,
                        "pending_tool": None,
                        "last_tool_result": rejected,
                        "messages": [*state.get("messages", []), _tool_message(name, rejected)],
                    }
        try:
            result = await registry.execute(name, args)
        except (NotFoundError, ValidationError) as exc:
            # F1: 模型选错工具/参数不对是常态——结构化失败观察回灌，让模型重试/换路
            error_code = "UNKNOWN_TOOL" if isinstance(exc, NotFoundError) else "INVALID_ARGS"
            result = ToolResult(ok=False, error_code=error_code, content=str(exc.message))
        return {
            "step_count": step + 1,
            "pending_tool": None,
            "last_tool_result": result,
            "messages": [*state.get("messages", []), _tool_message(name, result)],
        }

    def route_after_actor(state: AgentState) -> str:
        return "tool_executor" if state.get("action") == "call_tool" else "__end__"

    def route_after_executor(state: AgentState) -> str:
        # F2: 熔断/终止由 executor 发出，直接到 END，避免再进 actor 死循环
        return "actor" if state.get("status") != "budget_exceeded" else "__end__"

    builder = StateGraph(AgentState)
    builder.add_node("actor", actor)
    builder.add_node("tool_executor", tool_executor)
    builder.add_edge(START, "actor")
    builder.add_conditional_edges(
        "actor",
        route_after_actor,
        {"tool_executor": "tool_executor", "__end__": END},
    )
    builder.add_conditional_edges(
        "tool_executor",
        route_after_executor,
        {"actor": "actor", "__end__": END},
    )
    return builder.compile(checkpointer=checkpointer)
