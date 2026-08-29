"""CLI 客户端（F9.2）测试：FlareClient 经 ASGITransport 直连应用（不启真实服务器）。

覆盖：chat 非流式/流式重建、models、tasks/task、错误映射（HTTPStatusError）。
"""

from __future__ import annotations

import httpx
import pytest
from langgraph.checkpoint.memory import MemorySaver

from agent_runtime.app import create_app
from agent_runtime.tasks import TaskManager
from flare_cli.client import FlareClient
from flare_common.config import Settings
from model_gateway.mock import MockModelProvider
from tools_gateway.builtin import create_default_registry


async def _mem_saver():
    return MemorySaver()


def _app():
    manager = TaskManager(
        registry=create_default_registry(),
        llm=MockModelProvider(),
        checkpointer_factory=_mem_saver,
    )
    return create_app(settings=Settings(env="test"), task_manager=manager)


def _client() -> FlareClient:
    return FlareClient("http://test", transport=httpx.ASGITransport(app=_app()))


async def test_chat_non_stream_returns_content():
    client = _client()
    resp = await client.chat("hello")
    assert resp["object"] == "chat.completion"
    assert "echo: hello" in resp["choices"][0]["message"]["content"]


async def test_chat_stream_reconstructs_content():
    client = _client()
    parts = []
    async for delta in client.chat_stream("hello"):
        parts.append(delta)
    assert "echo: hello" in "".join(parts)


async def test_list_models():
    client = _client()
    models = await client.list_models()
    assert models and models[0]["id"] == "flare-agent"


async def test_tasks_list_and_get():
    client = _client()
    await client.chat("first")
    tasks = await client.list_tasks()
    assert tasks and tasks[0]["task_input"] == "first"
    got = await client.get_task(tasks[0]["task_id"])
    assert got["status"] == "completed"


async def test_unknown_task_raises_http_error():
    client = _client()
    with pytest.raises(httpx.HTTPStatusError):
        await client.get_task("nope")
