"""模型供应商抽象（A3）：agent-runtime 只依赖本接口，不依赖任何具体 SDK。

真实实现：OpenAI 兼容 HTTP 客户端（M4）；本地开发用 mock.py 的确定性实现。
chat / stream 均返回 usage，便于成本计量（ADR-0008 多供应商路由/配额）。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Protocol


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


class ModelProvider(Protocol):
    """统一模型入口。"""

    async def chat(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse: ...

    async def stream(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[str]: ...
