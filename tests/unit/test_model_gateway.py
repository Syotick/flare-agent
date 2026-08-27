"""模型供应商抽象与 mock 决策测试。"""

from __future__ import annotations

import json

from model_gateway.mock import MockModelProvider
from model_gateway.providers import LLMMessage


async def test_mock_decides_call_tool() -> None:
    provider = MockModelProvider()
    resp = await provider.chat([LLMMessage("user", "你好")])
    data = json.loads(resp.content)
    assert data["action"] == "call_tool"
    assert data["tool"]["name"] == "echo"
    assert data["tool"]["args"]["text"] == "你好"
    assert resp.model == "mock"


async def test_mock_decides_final_after_tool() -> None:
    provider = MockModelProvider()
    msgs = [LLMMessage("user", "你好"), LLMMessage("tool", "[echo] echo: 你好")]
    resp = await provider.chat(msgs)
    data = json.loads(resp.content)
    assert data["action"] == "final"
    assert "echo: 你好" in data["answer"]


async def test_mock_stream_word_chunks() -> None:
    provider = MockModelProvider()
    chunks = [c async for c in provider.stream([LLMMessage("user", "你好 世界")])]
    text = "".join(chunks).strip()
    assert json.loads(text)["action"] == "call_tool"
    assert len(chunks) > 1  # 词级分块（更像 token 流），非逐字符
