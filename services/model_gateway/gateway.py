"""模型网关（M4）：按配置装配供应商 + 瞬态重试。

真理：模型调用是 Agent 链路上最贵、最不稳定的环节——
  1. 统一入口（ModelProvider），上层不感知是 mock 还是 OpenAI；
  2. 可靠性（重试/超时）集中在网关层，供应商只管"单次传输+解析"；
  3. 成本/配额/降级/灰度（ADR-0008 全景）随 M5/M6 在此层继续扩展。
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from flare_common.config import Settings
from flare_common.errors import ValidationError
from model_gateway.mock import MockModelProvider
from model_gateway.openai_compat import OpenAICompatibleProvider, ProviderError
from model_gateway.providers import LLMMessage, LLMResponse, ModelProvider


class RetryProvider:
    """给任意供应商加瞬态重试（网络/超时/5xx），指数退避。

    只重试可重试错误；业务错误（4xx 校验、上游明确拒绝）不重试直接抛。
    """

    def __init__(
        self, provider: ModelProvider, *, max_retries: int = 2, base_delay: float = 0.5
    ) -> None:
        self._provider = provider
        self._max_retries = max_retries
        self._base_delay = base_delay

    async def chat(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                return await self._provider.chat(
                    messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    tools=tools,
                )
            except (ProviderError, TimeoutError, OSError) as exc:
                last_error = exc
                if attempt < self._max_retries:
                    await asyncio.sleep(self._base_delay * (2**attempt))
        assert last_error is not None
        raise last_error

    async def stream(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[str]:
        # 流已消费后无法安全重放，此处不做重试（文档注明：流式重试见 M5 语义层）
        async for chunk in self._provider.stream(messages, model=model, temperature=temperature):
            yield chunk

    async def close(self) -> None:
        if hasattr(self._provider, "close"):
            await self._provider.close()


def build_provider(settings: Settings) -> ModelProvider:
    """按配置装配供应商（mock | openai）。

    openai = OpenAI 兼容协议，覆盖 DeepSeek/DashScope/vLLM（改 base_url/api_key 即可）。
    """
    if settings.model_provider == "mock":
        return MockModelProvider()
    if settings.model_provider == "openai":
        base = OpenAICompatibleProvider(
            api_key=settings.model_api_key,
            base_url=settings.model_base_url,
            model=settings.model_name,
        )
        return RetryProvider(base)
    raise ValidationError(f"未知 model_provider: {settings.model_provider}（可选 mock|openai）")
