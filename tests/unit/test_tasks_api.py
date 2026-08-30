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


def test_delete_task() -> None:
    """会话管理：DELETE 移除任务，不存在则 404。"""
    app = create_app(task_manager=_manager())
    with TestClient(app) as client:
        created = client.post("/v1/tasks", json={"task_input": "bye"}).json()
        tid = created["task_id"]
        assert client.get(f"/v1/tasks/{tid}").status_code == 200
        assert client.delete(f"/v1/tasks/{tid}").status_code == 204
        assert client.get(f"/v1/tasks/{tid}").status_code == 404
        assert client.delete(f"/v1/tasks/{tid}").status_code == 404


# ---------- DSH 对齐：工作区（先选工作区，会话按工作区区分） ----------


def test_create_task_with_workspace() -> None:
    """创建任务可指定工作区；详情回传 workspace_id（默认 default）。"""
    app = create_app(task_manager=_manager())
    with TestClient(app) as client:
        created = client.post(
            "/v1/tasks", json={"task_input": "hi", "workspace_id": "proj-alpha"}
        ).json()
        assert created["workspace_id"] == "proj-alpha"
        done = _wait_done(client, created["task_id"])
    assert done["workspace_id"] == "proj-alpha"


def test_create_task_default_workspace() -> None:
    """未指定 workspace_id 时归入默认工作区。"""
    app = create_app(task_manager=_manager())
    with TestClient(app) as client:
        created = client.post("/v1/tasks", json={"task_input": "hi"}).json()
    assert created["workspace_id"] == "default"


def test_list_tasks_filter_by_workspace() -> None:
    """?workspace= 只返回该工作区会话；不带参数返回全量（兼容旧客户端）。"""
    app = create_app(task_manager=_manager())
    with TestClient(app) as client:
        a = client.post("/v1/tasks", json={"task_input": "in A", "workspace_id": "ws-a"}).json()
        b = client.post("/v1/tasks", json={"task_input": "in B", "workspace_id": "ws-b"}).json()
        _wait_done(client, a["task_id"])
        _wait_done(client, b["task_id"])
        only_a = client.get("/v1/tasks?workspace=ws-a").json()
        only_b = client.get("/v1/tasks?workspace=ws-b").json()
        all_tasks = client.get("/v1/tasks").json()
    ids_a = {t["task_id"] for t in only_a}
    ids_b = {t["task_id"] for t in only_b}
    assert a["task_id"] in ids_a and b["task_id"] not in ids_a
    assert b["task_id"] in ids_b and a["task_id"] not in ids_b
    assert a["task_id"] in {t["task_id"] for t in all_tasks}
    assert b["task_id"] in {t["task_id"] for t in all_tasks}


def test_workspaces_aggregate() -> None:
    """GET /v1/workspaces 聚合工作区（含默认），带会话计数。"""
    app = create_app(task_manager=_manager())
    with TestClient(app) as client:
        a = client.post("/v1/tasks", json={"task_input": "x", "workspace_id": "ws-alpha"}).json()
        _wait_done(client, a["task_id"])
        ws = client.get("/v1/workspaces").json()
    by_id = {w["workspace_id"]: w for w in ws}
    assert "ws-alpha" in by_id
    assert by_id["ws-alpha"]["task_count"] >= 1
    assert "default" in by_id  # 始终包含默认工作区
    # 按最近使用倒序（default 无会话时排在 ws-alpha 之后）
    assert ws[0]["workspace_id"] == "ws-alpha"
