"""模型供应商抽象与 mock 测试。"""

from __future__ import annotations

from model_gateway.mock import MockModelProvider
from model_gateway.providers import LLMMessage


async def test_mock_chat_echoes_last_message() -> None:
    provider = MockModelProvider()
    resp = await provider.chat([LLMMessage("user", "你好")])
    assert resp.model == "mock"
    assert "你好" in resp.content
    assert resp.usage.total_tokens > 0


async def test_mock_stream_word_chunks() -> None:
    provider = MockModelProvider()
    chunks = [c async for c in provider.stream([LLMMessage("user", "你好 世界")])]
    assert "".join(chunks).strip() == "[mock:user] 你好 世界"
    assert len(chunks) > 1  # 词级分块（更像 token 流），非逐字符
