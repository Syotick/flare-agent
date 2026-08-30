"""OpenAI 兼容 REST API 测试（F9.3）。

覆盖：非流式/流式 Chat Completions 契约、/v1/models、错误形状（OpenAI 风格）、
可选认证（FLARE_API_KEY）、任务确实被登记进 TaskManager。
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import MemorySaver

from agent_runtime.app import create_app
from agent_runtime.tasks import TaskManager
from flare_common.config import Settings
from model_gateway.mock import MockModelProvider
from tools_gateway.builtin import create_default_registry


async def _mem_saver():
    return MemorySaver()


def _manager() -> TaskManager:
    return TaskManager(
        registry=create_default_registry(),
        llm=MockModelProvider(),
        checkpointer_factory=_mem_saver,
    )


def _app(**kw):
    return create_app(settings=Settings(env="test"), task_manager=_manager(), **kw)


def test_chat_completions_non_stream() -> None:
    """F9.3：标准 Chat Completions 契约（非流式）。"""
    with TestClient(_app()) as client:
        resp = client.post(
            "/v1/chat/completions",
            json={"model": "flare-agent", "messages": [{"role": "user", "content": "hello"}]},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["object"] == "chat.completion"
    assert body["id"].startswith("chatcmpl-")
    assert body["model"] == "flare-agent"
    assert body["choices"][0]["finish_reason"] == "stop"
    assert body["choices"][0]["message"]["role"] == "assistant"
    assert "echo: hello" in body["choices"][0]["message"]["content"]
    assert body["usage"]["prompt_tokens"] > 0


async def test_chat_completions_uses_task_manager() -> None:
    """任务确实走 TaskManager（登记/可查，与 /v1/tasks 同一套）。"""
    manager = _manager()
    with TestClient(create_app(settings=Settings(env="test"), task_manager=manager)) as client:
        resp = client.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "hi"}]},
        )
        tid = resp.json()["id"].replace("chatcmpl-", "")
    task = await manager.get(tid)
    assert task is not None and task.done and task.status == "completed"


def test_chat_completions_stream() -> None:
    """流式：OpenAI chunk 格式 + [DONE]，拼接结果等于非流式结果。"""
    with TestClient(_app()) as client:
        resp = client.post(
            "/v1/chat/completions",
            json={
                "model": "flare-agent",
                "messages": [{"role": "user", "content": "hello"}],
                "stream": True,
            },
        )
    assert resp.status_code == 200
    text = resp.text
    assert "data: [DONE]" in text
    assert "chat.completion.chunk" in text
    content = "".join(
        _delta(line)
        for line in text.splitlines()
        if line.startswith("data: ") and not line.startswith("data: [DONE]")
    )
    assert "echo: hello" in content


def _delta(line: str) -> str:
    obj = json.loads(line[len("data: ") :])
    return obj["choices"][0]["delta"].get("content", "")


def test_models_endpoint() -> None:
    with TestClient(_app()) as client:
        body = client.get("/v1/models").json()
    assert body["object"] == "list"
    assert body["data"][0]["id"] == "flare-agent"


def test_missing_user_message_400_openai_error() -> None:
    with TestClient(_app()) as client:
        resp = client.post(
            "/v1/chat/completions", json={"messages": [{"role": "system", "content": "x"}]}
        )
    assert resp.status_code == 400
    err = resp.json()["error"]
    assert err["type"] == "invalid_request_error"
    assert err["code"] == "missing_user_message"


def test_auth_required_when_api_key_set() -> None:
    app = create_app(settings=Settings(env="test", api_key="sk-secret"), task_manager=_manager())
    payload = {"messages": [{"role": "user", "content": "hi"}]}
    with TestClient(app) as client:
        assert client.post("/v1/chat/completions", json=payload).status_code == 401
        assert client.get("/v1/models").status_code == 401
        ok = client.post(
            "/v1/chat/completions",
            json=payload,
            headers={"Authorization": "Bearer sk-secret"},
        )
    assert ok.status_code == 200
    assert ok.json()["object"] == "chat.completion"


def test_auth_open_when_no_key() -> None:
    with TestClient(_app()) as client:
        assert (
            client.post(
                "/v1/chat/completions", json={"messages": [{"role": "user", "content": "hi"}]}
            ).status_code
            == 200
        )
