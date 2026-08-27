"""模型供应商抽象（A3）：agent-runtime 只依赖本接口，不依赖任何具体 SDK。

真实实现：OpenAI 兼容 HTTP 客户端（M4）；本地开发用 mock.py 的确定性实现。
chat / stream 均返回 usage，便于成本计量（ADR-0008 多供应商路由/配额）。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field, model_validator


@dataclass
class LLMMessage:
    role: str  # system | user | assistant | tool
    content: str


@dataclass
class LLMUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass
class LLMResponse:
    content: str
    model: str
    usage: LLMUsage = field(default_factory=LLMUsage)


class ToolCall(BaseModel):
    """模型要调用的工具（与真实 function-calling 同形态）。"""

    name: str
    args: dict[str, Any] = Field(default_factory=dict)


class ToolCallDecision(BaseModel):
    """模型决策契约（F3）：mock 产出与 graph 解析共享的唯一结构。

    - call_tool: 必须携带 tool
    - final: 携带最终回答 answer
    字段漂移（改名/类型变化/新增 action）在构造/校验时即报错，杜绝两处手写约定。
    """

    action: Literal["call_tool", "final"]
    tool: ToolCall | None = None
    answer: str | None = None

    @model_validator(mode="after")
    def _require_tool_when_call(self) -> ToolCallDecision:
        if self.action == "call_tool" and self.tool is None:
            raise ValueError("call_tool 决策必须携带 tool")
        return self


class ModelProvider(Protocol):
    """统一模型入口。"""

    async def chat(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: list[dict] | None = None,  # M4：原生 function-calling 工具清单（OpenAI 形态）
    ) -> LLMResponse: ...

    async def stream(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[str]: ...
