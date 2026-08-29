"""Anthropic 原生协议供应商（Claude Messages API）。

与 openai_compat 平行：同一个 ModelProvider 契约。内部历史 -> Anthropic wire 格式
（assistant 的 tool_use 块 + 紧随 tool 结果的 user tool_result 块），响应解析
tool_use -> call_tool 决策 JSON（与 mock/openai 同形态，graph._parse_decision 唯一解析点）。

协议差异点（坑，与 OpenAI 不同）：
- 端点是 /v1/messages（不是 /chat/completions）；认证用 x-api-key + anthropic-version 头
- max_tokens 必填（无默认，缺失 400）
- 工具：assistant 消息 content 是 block 数组（text / tool_use），工具结果放
  "下一条 user 消息"的 tool_result 块（不是独立 tool 角色）
- 响应无 choices：content 数组里 type=text / type=tool_use；usage 字段叫 input/output_tokens
- 流式：SSE 事件 content_block_delta 的 delta.text_delta.text
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator

import httpx

from model_gateway.openai_compat import ProviderError  # 复用瞬态错误契约
from model_gateway.providers import (
    LLMMessage,
    LLMResponse,
    LLMUsage,
    ToolCall,
    ToolCallDecision,
)

MESSAGES_ENDPOINT = "/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


def _try_parse_decision(content: str) -> ToolCallDecision | None:
    """宽松解析：assistant 消息里若是决策 JSON 就还原成契约；否则视为普通文本。"""
    try:
        return ToolCallDecision.model_validate(json.loads(content))
    except Exception:  # noqa: BLE001 - 非决策文本是正常情况
        return None


def _to_anthropic_tools(tools: list[dict] | None) -> list[dict] | None:
    """OpenAI 形态工具清单 -> Anthropic input_schema 形态。"""
    if not tools:
        return None
    out: list[dict] = []
    for t in tools:
        fn = t.get("function") or {}
        out.append(
            {
                "name": fn.get("name", ""),
                "description": fn.get("description", ""),
                "input_schema": fn.get("parameters") or {"type": "object", "properties": {}},
            }
        )
    return out or None


def _serialize_messages(messages: list[LLMMessage]) -> tuple[str, list[dict]]:
    """内部历史 -> Anthropic messages（system 单独提取 + tool_use/tool_result 配对）。

    返回 (system, wire_messages)。Anthropic 要求 user/assistant 交替：
    assistant(tool_use) 之后必须跟 user(tool_result) 再跟 assistant。
    """
    system_parts: list[str] = []
    wire: list[dict] = []
    pending_tool_use_id: str | None = None
    for m in messages:
        if m.role == "system":
            system_parts.append(m.content)
            continue
        if m.role == "user":
            pending_tool_use_id = None
            wire.append({"role": "user", "content": m.content})
            continue
        if m.role == "assistant":
            decision = _try_parse_decision(m.content)
            if decision and decision.action == "call_tool" and decision.tool is not None:
                tid = "toolu_" + uuid.uuid4().hex[:20]
                wire.append(
                    {
                        "role": "assistant",
                        "content": [
                            {
                                "type": "tool_use",
                                "id": tid,
                                "name": decision.tool.name,
                                "input": decision.tool.args,
                            }
                        ],
                    }
                )
                pending_tool_use_id = tid
                continue
            wire.append({"role": "assistant", "content": m.content})
            continue
        # role == tool：观察结果 -> 包进 user 的 tool_result 块（配对上一条 tool_use）
        if pending_tool_use_id is not None:
            wire.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": pending_tool_use_id,
                            "content": m.content,
                        }
                    ],
                }
            )
            pending_tool_use_id = None
        else:
            # 兜底：理论不发生（tool 必跟在 tool_use 后），保文本可读
            wire.append({"role": "user", "content": f"[工具结果] {m.content}"})
    return ("\n\n".join(system_parts), wire)


def _decision_from_wire(data: dict) -> str:
    """Anthropic 响应 -> 决策 JSON（与 mock 同形态，graph 层统一解析）。"""
    blocks = data.get("content") or []
    for block in blocks:
        if block.get("type") == "tool_use":
            decision = ToolCallDecision(
                action="call_tool",
                tool=ToolCall(name=block.get("name", ""), args=block.get("input") or {}),
            )
            return decision.model_dump_json()
    text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
    return ToolCallDecision(action="final", answer=text).model_dump_json()


def _parse_usage(data: dict) -> LLMUsage:
    u = data.get("usage") or {}
    return LLMUsage(
        prompt_tokens=u.get("input_tokens", 0), completion_tokens=u.get("output_tokens", 0)
    )


class AnthropicCompatibleProvider:
    """Anthropic / Claude 原生协议供应商（同一 /v1/messages 协议）。"""

    def __init__(
        self,
        *,
        api_key: str = "",
        base_url: str = "https://api.anthropic.com",
        model: str = "claude-sonnet-4-5",
        timeout: float = 30.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._client = http_client or httpx.AsyncClient(timeout=timeout)
        self._owns_client = http_client is None
        # base_url 兼容两种写法：https://api.anthropic.com 或 .../v1
        if self._base_url.endswith("/v1"):
            self._messages_url = self._base_url + "/messages"
        else:
            self._messages_url = self._base_url + MESSAGES_ENDPOINT

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "anthropic-version": ANTHROPIC_VERSION}
        if self._api_key:
            headers["x-api-key"] = self._api_key
        return headers

    async def chat(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        system, wire = _serialize_messages(messages)
        payload: dict = {
            "model": model or self._model,
            "max_tokens": max_tokens or 2048,  # Anthropic 必填，无默认
            "messages": wire,
        }
        if system:
            payload["system"] = system
        if temperature is not None:
            payload["temperature"] = temperature
        anthropic_tools = _to_anthropic_tools(tools)
        if anthropic_tools:
            payload["tools"] = anthropic_tools
            payload["tool_choice"] = {"type": "auto"}
        resp = await self._client.post(self._messages_url, json=payload, headers=self._headers())
        if resp.status_code >= 500:
            raise ProviderError(f"上游 {resp.status_code}: {resp.text[:200]}")
        resp.raise_for_status()
        data = resp.json()
        return LLMResponse(
            content=_decision_from_wire(data),
            model=data.get("model", self._model),
            usage=_parse_usage(data),
        )

    async def stream(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[str]:
        system, wire = _serialize_messages(messages)
        payload: dict = {
            "model": model or self._model,
            "max_tokens": 2048,
            "messages": wire,
            "stream": True,
        }
        if system:
            payload["system"] = system
        if temperature is not None:
            payload["temperature"] = temperature
        async with self._client.stream(
            "POST", self._messages_url, json=payload, headers=self._headers()
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                raw = line[6:].strip()
                if not raw or raw == "[DONE]":
                    continue
                try:
                    chunk = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if chunk.get("type") == "content_block_delta":
                    delta = chunk.get("delta") or {}
                    if delta.get("type") == "text_delta" and delta.get("text"):
                        yield delta["text"]

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()
