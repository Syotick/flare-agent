"""模型网关测试（M4）：OpenAI 兼容供应商 wire 序列化 / 原生工具映射 / 重试 / 流式 / 工厂。"""

from __future__ import annotations

import json

import httpx
import pytest
from httpx import AsyncClient, MockTransport, Response

from flare_common.config import Settings
from flare_common.errors import ValidationError
from model_gateway.anthropic_compat import AnthropicCompatibleProvider
from model_gateway.gateway import RetryProvider, build_provider
from model_gateway.mock import MockModelProvider
from model_gateway.openai_compat import OpenAICompatibleProvider, ProviderError
from model_gateway.providers import LLMMessage, ToolCall, ToolCallDecision


def _json_response(payload: dict, status: int = 200) -> Response:
    return Response(status, json=payload)


def _final_payload(content: str = "答案是 42") -> dict:
    return {
        "id": "chatcmpl-test",
        "model": "gpt-4o-mini",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }


async def test_native_tool_call_mapped_to_decision() -> None:
    def handler(request: httpx.Request) -> Response:
        return _json_response(
            {
                "model": "gpt-4o-mini",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_abc",
                                    "type": "function",
                                    "function": {
                                        "name": "kb_search",
                                        "arguments": '{"query": "部署", "k": 3}',
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            }
        )

    client = AsyncClient(transport=MockTransport(handler))
    provider = OpenAICompatibleProvider(base_url="http://test/v1", http_client=client)
    resp = await provider.chat([LLMMessage(role="user", content="hi")])
    decision = ToolCallDecision.model_validate_json(resp.content)
    assert decision.action == "call_tool"
    assert decision.tool is not None and decision.tool.name == "kb_search"
    assert decision.tool.args == {"query": "部署", "k": 3}
    assert resp.usage.total_tokens == 15
    await client.aclose()


async def test_plain_text_mapped_to_final() -> None:
    def handler(request: httpx.Request) -> Response:
        return _json_response(_final_payload())

    client = AsyncClient(transport=MockTransport(handler))
    provider = OpenAICompatibleProvider(base_url="http://test/v1", http_client=client)
    resp = await provider.chat([LLMMessage(role="user", content="hi")])
    decision = ToolCallDecision.model_validate_json(resp.content)
    assert decision.action == "final"
    assert decision.answer == "答案是 42"
    await client.aclose()


async def test_wire_serialization_rebuilds_tool_calls_and_pairs_id() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> Response:
        captured["body"] = json.loads(request.content)
        return _json_response(_final_payload())

    call = ToolCallDecision(action="call_tool", tool=ToolCall(name="echo", args={"text": "hi"}))
    msgs = [
        LLMMessage(role="system", content="sys"),
        LLMMessage(role="user", content="u"),
        LLMMessage(role="assistant", content=call.model_dump_json()),
        LLMMessage(role="tool", content="[echo] hi"),
    ]
    client = AsyncClient(transport=MockTransport(handler))
    provider = OpenAICompatibleProvider(base_url="http://test/v1", http_client=client)
    await provider.chat(msgs, tools=[{"type": "function", "function": {"name": "echo"}}])
    wire = captured["body"]["messages"]
    assert wire[2]["role"] == "assistant"
    assert wire[2]["content"] is None
    assert wire[2]["tool_calls"][0]["function"]["name"] == "echo"
    assert json.loads(wire[2]["tool_calls"][0]["function"]["arguments"]) == {"text": "hi"}
    cid = wire[2]["tool_calls"][0]["id"]
    assert wire[3] == {"role": "tool", "tool_call_id": cid, "content": "[echo] hi"}
    # tools 透传给上游
    assert captured["body"]["tools"][0]["function"]["name"] == "echo"
    await client.aclose()


async def test_retry_provider_recovers_from_500() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> Response:
        calls.append(1)
        if len(calls) == 1:
            return Response(500, text="upstream boom")
        return _json_response(_final_payload("recovered"))

    client = AsyncClient(transport=MockTransport(handler))
    base = OpenAICompatibleProvider(base_url="http://test/v1", http_client=client)
    retry = RetryProvider(base, max_retries=1, base_delay=0.01)
    resp = await retry.chat([LLMMessage(role="user", content="hi")])
    assert len(calls) == 2
    assert ToolCallDecision.model_validate_json(resp.content).answer == "recovered"
    await client.aclose()


async def test_retry_provider_gives_up() -> None:
    def handler(request: httpx.Request) -> Response:
        return Response(500, text="always down")

    client = AsyncClient(transport=MockTransport(handler))
    base = OpenAICompatibleProvider(base_url="http://test/v1", http_client=client)
    retry = RetryProvider(base, max_retries=1, base_delay=0.01)
    with pytest.raises(ProviderError):
        await retry.chat([LLMMessage(role="user", content="hi")])
    await client.aclose()


async def test_stream_parses_sse() -> None:
    sse = (
        b'data: {"choices":[{"delta":{"role":"assistant"}}]}\n\n'
        b'data: {"choices":[{"delta":{"content":"\u4f60\u597d"}}]}\n\n'
        b'data: {"choices":[{"delta":{"content":"\u4e16\u754c"}}]}\n\n'
        b"data: [DONE]\n\n"
    )

    def handler(request: httpx.Request) -> Response:
        return Response(200, content=sse, headers={"content-type": "text/event-stream"})

    client = AsyncClient(transport=MockTransport(handler))
    provider = OpenAICompatibleProvider(base_url="http://test/v1", http_client=client)
    chunks: list[str] = []
    async for c in provider.stream([LLMMessage(role="user", content="hi")]):
        chunks.append(c)
    assert chunks == ["你好", "世界"]
    await client.aclose()


def test_build_provider_factory() -> None:
    assert isinstance(build_provider(Settings(model_provider="mock")), MockModelProvider)
    p = build_provider(
        Settings(model_provider="openai", model_base_url="http://x/v1", model_name="m")
    )
    assert isinstance(p, RetryProvider)
    with pytest.raises(ValidationError):
        build_provider(Settings(model_provider="nope"))


async def test_anthropic_tool_use_mapped_to_decision() -> None:
    def handler(request: httpx.Request) -> Response:
        return _json_response(
            {
                "id": "msg_test",
                "model": "claude-sonnet-4-5",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu_1",
                        "name": "kb_search",
                        "input": {"query": "部署", "k": 3},
                    }
                ],
                "stop_reason": "tool_use",
                "usage": {"input_tokens": 10, "output_tokens": 5},
            }
        )

    client = AsyncClient(transport=MockTransport(handler))
    provider = AnthropicCompatibleProvider(base_url="http://test", http_client=client)
    resp = await provider.chat([LLMMessage(role="user", content="hi")])
    decision = ToolCallDecision.model_validate_json(resp.content)
    assert decision.action == "call_tool"
    assert decision.tool is not None and decision.tool.name == "kb_search"
    assert decision.tool.args == {"query": "部署", "k": 3}
    assert resp.usage.total_tokens == 15
    await client.aclose()


async def test_anthropic_text_mapped_to_final() -> None:
    def handler(request: httpx.Request) -> Response:
        return _json_response(
            {
                "id": "msg_test",
                "model": "claude-sonnet-4-5",
                "content": [{"type": "text", "text": "你好，Claude"}],
                "usage": {"input_tokens": 3, "output_tokens": 2},
            }
        )

    client = AsyncClient(transport=MockTransport(handler))
    provider = AnthropicCompatibleProvider(base_url="http://test", http_client=client)
    resp = await provider.chat([LLMMessage(role="user", content="hi")])
    decision = ToolCallDecision.model_validate_json(resp.content)
    assert decision.action == "final"
    assert decision.answer == "你好，Claude"
    await client.aclose()


async def test_anthropic_wire_serialization_tool_result_pairs() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> Response:
        captured["body"] = json.loads(request.content)
        captured["headers"] = dict(request.headers)
        return _json_response(
            {
                "id": "msg_test",
                "model": "claude-sonnet-4-5",
                "content": [{"type": "text", "text": "ok"}],
                "usage": {},
            }
        )

    call = ToolCallDecision(action="call_tool", tool=ToolCall(name="echo", args={"text": "hi"}))
    msgs = [
        LLMMessage(role="system", content="sys"),
        LLMMessage(role="user", content="u"),
        LLMMessage(role="assistant", content=call.model_dump_json()),
        LLMMessage(role="tool", content="[echo] hi"),
    ]
    client = AsyncClient(transport=MockTransport(handler))
    provider = AnthropicCompatibleProvider(
        base_url="http://test", api_key="sk-ant", http_client=client
    )
    await provider.chat(msgs, tools=[{"type": "function", "function": {"name": "echo"}}])
    body = captured["body"]
    assert body["system"] == "sys"
    assert body["max_tokens"] == 2048  # Anthropic 必填
    wire = body["messages"]
    assert wire[0] == {"role": "user", "content": "u"}
    assert wire[1]["role"] == "assistant"
    assert wire[1]["content"][0]["type"] == "tool_use"
    assert wire[1]["content"][0]["name"] == "echo"
    assert wire[1]["content"][0]["input"] == {"text": "hi"}
    tid = wire[1]["content"][0]["id"]
    assert wire[2] == {
        "role": "user",
        "content": [{"type": "tool_result", "tool_use_id": tid, "content": "[echo] hi"}],
    }
    # 认证头 + 工具转 input_schema
    assert captured["headers"]["x-api-key"] == "sk-ant"
    assert captured["headers"]["anthropic-version"] == "2023-06-01"
    assert body["tools"][0]["name"] == "echo"
    assert body["tools"][0]["input_schema"] == {"type": "object", "properties": {}}
    await client.aclose()


async def test_anthropic_stream_parses_sse() -> None:
    sse = (
        'data: {"type":"content_block_delta",'
        '"delta":{"type":"text_delta","text":"\\u4f60\\u597d"}}\n\n'
        'data: {"type":"content_block_delta",'
        '"delta":{"type":"text_delta","text":"\\u4e16\\u754c"}}\n\n'
        'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"}}\n\n'
    ).encode("ascii")

    def handler(request: httpx.Request) -> Response:
        return Response(200, content=sse, headers={"content-type": "text/event-stream"})

    client = AsyncClient(transport=MockTransport(handler))
    provider = AnthropicCompatibleProvider(base_url="http://test", http_client=client)
    chunks: list[str] = []
    async for c in provider.stream([LLMMessage(role="user", content="hi")]):
        chunks.append(c)
    assert chunks == ["你好", "世界"]
    await client.aclose()


def test_build_provider_anthropic() -> None:
    p = build_provider(
        Settings(
            model_provider="anthropic",
            model_base_url="https://api.anthropic.com",
            model_name="claude-sonnet-4-5",
        )
    )
    assert isinstance(p, RetryProvider)
