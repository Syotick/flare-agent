"""确定性 Mock 供应商（无网络/无 Key）：本地开发与单元测试。"""

from __future__ import annotations

from collections.abc import AsyncIterator

from model_gateway.providers import LLMMessage, LLMResponse, LLMUsage


class MockModelProvider:
    """根据最后一条消息给出可复现的回复，供 LangGraph 图测试/演示。"""

    model: str = "mock"

    async def chat(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        last = messages[-1] if messages else LLMMessage("user", "")
        content = f"[mock:{last.role}] {last.content}"
        prompt_tokens = sum(len(m.content) for m in messages)
        return LLMResponse(
            content=content,
            model=model or self.model,
            usage=LLMUsage(prompt_tokens=prompt_tokens, completion_tokens=len(content)),
        )

    async def stream(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[str]:
        response = await self.chat(messages, model=model, temperature=temperature)
        # 词级分块（更接近真实 token 流形状），勿让上层形成"逐字符"依赖（R4）
        for word in response.content.split(" "):
            yield word + " "
