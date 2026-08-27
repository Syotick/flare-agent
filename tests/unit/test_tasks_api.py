"""任务 API 测试（M2-4c 端到端回路：POST 任务 → SSE 轨迹 → 结果）。"""

from __future__ import annotations

from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import MemorySaver

from agent_runtime.app import create_app
from agent_runtime.tasks import TaskManager
from model_gateway.mock import MockModelProvider
from tools_gateway.builtin import create_default_registry


async def _mem_saver():
    return MemorySaver()


def _manager() -> TaskManager:
    # 内存 checkpoint，避免 API 测试写 SQLite 文件
    return TaskManager(
        registry=create_default_registry(),
        llm=MockModelProvider(),
        checkpointer_factory=_mem_saver,
    )


def test_create_task_completes() -> None:
    app = create_app(task_manager=_manager())
    with TestClient(app) as client:
        resp = client.post("/v1/tasks", json={"task_input": "hello"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert "echo: hello" in body["result"]["output"]
    assert body["result"]["step_count"] >= 1


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
