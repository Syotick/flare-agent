"""确定性 Mock 供应商（无网络/无 Key）：本地开发与单元测试。

模拟"会调用 echo 工具、能观察结果给出结论"的模型，返回结构化 JSON 决策串
（与真实 function-calling 同形态，graph 层负责解析）：
  - 需要工具: {"action": "call_tool", "tool": {"name": "echo", "args": {"text": <首个 user 消息>}}}
  - 已有工具观察: {"action": "final", "answer": "完成: <观察内容>"}
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from model_gateway.providers import (
    LLMMessage,
    LLMResponse,
    LLMUsage,
    ToolCall,
    ToolCallDecision,
)


class MockModelProvider:
    """确定性 mock 供应商。"""

    model: str = "mock"

    def _decide(self, messages: list[LLMMessage]) -> ToolCallDecision:
        last = messages[-1] if messages else None
        if last is not None and last.role == "tool":
            return ToolCallDecision(action="final", answer=f"完成: {last.content}")
        user_text = next((m.content for m in messages if m.role == "user"), "")
        return ToolCallDecision(
            action="call_tool", tool=ToolCall(name="echo", args={"text": user_text})
        )

    async def chat(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        content = self._decide(messages).model_dump_json()
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
