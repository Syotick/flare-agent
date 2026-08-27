"""OpenAI 兼容供应商（M4）：走真实 HTTP，原生 function-calling。

职责：
- 把内部历史 LLMMessage 序列化成 wire 格式：assistant 决策 JSON 还原为原生 tool_calls，
  并与随后的 role=tool 消息配对 tool_call_id（OpenAI 强制要求，缺失会 400）；
- 解析响应：有 tool_calls -> call_tool 决策 JSON；纯文本 -> final 决策 JSON
  （graph._parse_decision 是唯一解析点，与 mock 同形态，M4 核心映射）；
- 支持超时/usage 计量；重试/降级交给 gateway 层（RetryProvider），本类只做单次传输+解析。
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator

import httpx

from model_gateway.providers import (
    LLMMessage,
    LLMResponse,
    LLMUsage,
    ToolCall,
    ToolCallDecision,
)

CHAT_ENDPOINT = "/chat/completions"


class ProviderError(Exception):
    """上游可重试的瞬态错误（网络/超时/5xx）。"""


def _try_parse_decision(content: str) -> ToolCallDecision | None:
    """宽松解析：assistant 消息里若是决策 JSON 就还原成契约；否则视为普通文本。"""
    try:
        return ToolCallDecision.model_validate(json.loads(content))
    except Exception:  # noqa: BLE001 - 非决策文本是正常情况
        return None


def _serialize_messages(messages: list[LLMMessage]) -> list[dict]:
    """内部历史 -> OpenAI wire 格式，重建 tool_calls 并配对 tool_call_id。

    assistant(call_tool 决策) 还原为 content=null + tool_calls，
    紧跟其后的 role=tool 消息用同一 id（一对一手账），保证真实 API 接受。
    """
    wire: list[dict] = []
    pending_tool_call_id: str | None = None
    for m in messages:
        if m.role == "assistant":
            decision = _try_parse_decision(m.content)
            if decision and decision.action == "call_tool" and decision.tool is not None:
                cid = "call_" + uuid.uuid4().hex[:10]
                wire.append(
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": cid,
                                "type": "function",
                                "function": {
                                    "name": decision.tool.name,
                                    "arguments": json.dumps(decision.tool.args, ensure_ascii=False),
                                },
                            }
                        ],
                    }
                )
                pending_tool_call_id = cid
                continue
            wire.append({"role": "assistant", "content": m.content})
        elif m.role == "tool":
            wire.append(
                {
                    "role": "tool",
                    "tool_call_id": pending_tool_call_id or "call_legacy",
                    "content": m.content,
                }
            )
            pending_tool_call_id = None
        else:  # system | user
            wire.append({"role": m.role, "content": m.content})
    return wire


def _decision_from_wire(data: dict) -> str:
    """上游响应 -> 决策 JSON（与 mock 同形态，graph 层统一解析）。"""
    choices = data.get("choices") or []
    if not choices:
        raise ProviderError("上游返回无 choices")
    msg = choices[0].get("message") or {}
    tool_calls = msg.get("tool_calls") or []
    if tool_calls:
        fn = tool_calls[0].get("function") or {}
        try:
            args = json.loads(fn.get("arguments") or "{}")
        except json.JSONDecodeError:
            args = {}
        decision = ToolCallDecision(
            action="call_tool", tool=ToolCall(name=fn.get("name", ""), args=args)
        )
    else:
        decision = ToolCallDecision(action="final", answer=msg.get("content") or "")
    return decision.model_dump_json()


def _parse_usage(data: dict) -> LLMUsage:
    u = data.get("usage") or {}
    return LLMUsage(
        prompt_tokens=u.get("prompt_tokens", 0), completion_tokens=u.get("completion_tokens", 0)
    )


class OpenAICompatibleProvider:
    """OpenAI / DeepSeek / DashScope / vLLM 兼容供应商（同一 /chat/completions 协议）。"""

    def __init__(
        self,
        *,
        api_key: str = "",
        base_url: str = "http://localhost:9001/v1",
        model: str = "gpt-4o-mini",
        timeout: float = 30.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._client = http_client or httpx.AsyncClient(timeout=timeout)
        self._owns_client = http_client is None

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
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
        payload: dict = {
            "model": model or self._model,
            "messages": _serialize_messages(messages),
            "stream": False,
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if tools:
            payload["tools"] = tools
        resp = await self._client.post(
            self._base_url + CHAT_ENDPOINT, json=payload, headers=self._headers()
        )
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
        payload: dict = {
            "model": model or self._model,
            "messages": _serialize_messages(messages),
            "stream": True,
        }
        if temperature is not None:
            payload["temperature"] = temperature
        async with self._client.stream(
            "POST", self._base_url + CHAT_ENDPOINT, json=payload, headers=self._headers()
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                if delta.get("content"):
                    yield delta["content"]

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()
