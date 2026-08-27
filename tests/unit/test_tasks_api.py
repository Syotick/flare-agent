"""任务 API 测试（L1 真·流式：POST 立即返回，后台执行，SSE 实时）。"""

from __future__ import annotations

import time

from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import MemorySaver

from agent_runtime.app import create_app
from agent_runtime.tasks import TaskManager
from model_gateway.mock import MockModelProvider
from tools_gateway.builtin import create_default_registry

TERMINAL = ("completed", "budget_exceeded", "failed")


async def _mem_saver():
    return MemorySaver()


def _manager() -> TaskManager:
    return TaskManager(
        registry=create_default_registry(),
        llm=MockModelProvider(),
        checkpointer_factory=_mem_saver,
    )


def _wait_done(client, task_id, timeout=5.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get(f"/v1/tasks/{task_id}").json()
        if body["status"] in TERMINAL:
            return body
        time.sleep(0.02)
    raise AssertionError(f"task {task_id} 未在 {timeout}s 内结束: {body['status']}")


def test_create_task_returns_immediately() -> None:
    """L1: POST 立即返回(202)，不被任务耗时阻塞。"""
    app = create_app(task_manager=_manager())
    with TestClient(app) as client:
        resp = client.post("/v1/tasks", json={"task_input": "hello"})
    assert resp.status_code == 202
    body = resp.json()
    assert body["task_id"]
    assert "result" not in body  # 立即返回，不携带结果


def test_task_completes_with_result() -> None:
    app = create_app(task_manager=_manager())
    with TestClient(app) as client:
        created = client.post("/v1/tasks", json={"task_input": "hello"}).json()
        done = _wait_done(client, created["task_id"])
    assert done["status"] == "completed"
    assert "echo: hello" in done["result"]["output"]
    assert done["event_count"] >= 1


def test_task_stream_replays_trajectory() -> None:
    app = create_app(task_manager=_manager())
    with TestClient(app) as client:
        created = client.post("/v1/tasks", json={"task_input": "hi"}).json()
        stream = client.get(f"/v1/tasks/{created['task_id']}/stream")
    assert stream.status_code == 200
    assert stream.headers["content-type"].startswith("text/event-stream")
    text = stream.text
    assert "event: step" in text
    assert "event: result" in text
    assert "echo: hi" in text


def test_list_tasks() -> None:
    app = create_app(task_manager=_manager())
    with TestClient(app) as client:
        created = client.post("/v1/tasks", json={"task_input": "a"}).json()
        lst = client.get("/v1/tasks").json()
    assert any(t["task_id"] == created["task_id"] for t in lst)


def test_unknown_task_stream_404() -> None:
    app = create_app(task_manager=_manager())
    with TestClient(app) as client:
        resp = client.get("/v1/tasks/nope/stream")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "NOT_FOUND"


def test_empty_task_input_422() -> None:
    app = create_app(task_manager=_manager())
    with TestClient(app) as client:
        resp = client.post("/v1/tasks", json={"task_input": ""})
    assert resp.status_code == 422
