"""FlareClient：连接 Flare Agent HTTP API 的瘦客户端（F9.2/F9.3）。

- 走 OpenAI 兼容 /v1/chat/completions（chat）、/v1/models（models）
- 走原生 /v1/tasks（tasks / task，SSE 流）
- 可注入 httpx.ASGITransport 供测试（不启真实服务器）
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

DEFAULT_URL = "http://127.0.0.1:8000"


class FlareClient:
    def __init__(
        self,
        base_url: str = DEFAULT_URL,
        *,
        api_key: str = "",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        kwargs: dict = {"base_url": self._base, "headers": self._headers, "timeout": 30.0}
        if self._transport is not None:
            kwargs["transport"] = self._transport
        return httpx.AsyncClient(**kwargs)

    async def list_models(self) -> list[dict]:
        async with self._client() as c:
            resp = await c.get("/v1/models")
            resp.raise_for_status()
            return list((resp.json() or {}).get("data", []))

    async def chat(self, prompt: str, *, model: str = "flare-agent", max_steps: int = 5) -> dict:
        """非流式 Chat Completions，返回完整 OpenAI 响应对象。"""
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_steps": max_steps,
            "stream": False,
        }
        async with self._client() as c:
            resp = await c.post("/v1/chat/completions", json=payload)
            resp.raise_for_status()
            return resp.json()

    async def chat_stream(
        self, prompt: str, *, model: str = "flare-agent", max_steps: int = 5
    ) -> AsyncIterator[str]:
        """流式 Chat Completions：逐 delta 产出 content 片段。"""
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_steps": max_steps,
            "stream": True,
        }
        async with (
            self._client() as c,
            c.stream("POST", "/v1/chat/completions", json=payload) as resp,
        ):
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                line = line.strip()
                if not line.startswith("data:"):
                    continue
                data = line[len("data:") :].strip()
                if data == "[DONE]":
                    return
                try:
                    obj = json.loads(data)
                    delta = obj["choices"][0]["delta"].get("content", "")
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue
                if delta:
                    yield delta

    async def list_tasks(self) -> list[dict]:
        async with self._client() as c:
            resp = await c.get("/v1/tasks")
            resp.raise_for_status()
            return list(resp.json() or [])

    async def get_task(self, task_id: str) -> dict:
        async with self._client() as c:
            resp = await c.get(f"/v1/tasks/{task_id}")
            resp.raise_for_status()
            return resp.json()

    async def stream_task(self, task_id: str) -> AsyncIterator[str]:
        """原生任务 SSE 流（原始事件块）。"""
        async with (
            self._client() as c,
            c.stream("GET", f"/v1/tasks/{task_id}/stream") as resp,
        ):
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line.strip():
                    yield line
