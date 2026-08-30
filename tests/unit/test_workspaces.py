"""工作区目录 API 测试（DSH browse 对齐：目录浏览 / 创建 / 错误契约）。

后端作为 Host 角色，工作区 = 服务器真实目录路径。
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from agent_runtime.app import create_app
from agent_runtime.tasks import TaskManager
from model_gateway.mock import MockModelProvider
from tools_gateway.builtin import create_default_registry

TERMINAL = ("completed", "budget_exceeded", "failed")


def _manager() -> TaskManager:
    return TaskManager(
        registry=create_default_registry(),
        llm=MockModelProvider(),
    )


def _wait_done(client, task_id, timeout=5.0) -> dict:
    import time

    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get(f"/v1/tasks/{task_id}").json()
        if body["status"] in TERMINAL:
            return body
        time.sleep(0.02)
    raise AssertionError(f"task {task_id} 未在 {timeout}s 内结束: {body['status']}")


def test_list_dirs_root() -> None:
    """根级（path 为空）：Windows 盘符 / POSIX /，全为目录。"""
    app = create_app(task_manager=_manager())
    with TestClient(app) as client:
        r = client.get("/v1/workspaces/dirs").json()
    assert "path" in r and "entries" in r and r["truncated"] is False
    assert len(r["entries"]) >= 1
    assert all(e["is_dir"] for e in r["entries"])


def test_list_dirs_project(tmp_path) -> None:
    """列目录：子目录可见，parent 用于向上导航。"""
    (tmp_path / "docs").mkdir()
    (tmp_path / "note.txt").write_text("x")
    (tmp_path / ".hidden").mkdir()
    app = create_app(task_manager=_manager())
    with TestClient(app) as client:
        r = client.get("/v1/workspaces/dirs", params={"path": str(tmp_path)}).json()
    names = [e["name"] for e in r["entries"]]
    assert "docs" in names
    assert "note.txt" not in names  # 只列目录，不列文件
    assert ".hidden" in names  # 隐藏项返回，由前端过滤显示
    assert r["parent"] is not None


def test_list_dirs_missing(tmp_path) -> None:
    """不存在目录 -> 404 DIR_NOT_FOUND。"""
    app = create_app(task_manager=_manager())
    with TestClient(app) as client:
        resp = client.get("/v1/workspaces/dirs", params={"path": str(tmp_path / "nope")})
    assert resp.status_code == 404
    assert resp.json()["code"] == "DIR_NOT_FOUND"


def test_list_dirs_not_a_dir(tmp_path) -> None:
    """路径是文件而非目录 -> 422 NOT_A_DIR。"""
    f = tmp_path / "a.txt"
    f.write_text("x")
    app = create_app(task_manager=_manager())
    with TestClient(app) as client:
        resp = client.get("/v1/workspaces/dirs", params={"path": str(f)})
    assert resp.status_code == 422
    assert resp.json()["code"] == "NOT_A_DIR"


def test_create_dir(tmp_path) -> None:
    """创建目录成功：返回绝对路径且真实存在。"""
    app = create_app(task_manager=_manager())
    with TestClient(app) as client:
        r = client.post("/v1/workspaces/dirs", json={"path": str(tmp_path), "name": "my-ws"})
    assert r.status_code == 201
    assert (tmp_path / "my-ws").is_dir()
    assert r.json()["path"] == str(tmp_path / "my-ws")


def test_create_dir_conflict(tmp_path) -> None:
    """已存在 -> 409 ALREADY_EXISTS。"""
    (tmp_path / "dup").mkdir()
    app = create_app(task_manager=_manager())
    with TestClient(app) as client:
        resp = client.post("/v1/workspaces/dirs", json={"path": str(tmp_path), "name": "dup"})
    assert resp.status_code == 409
    assert resp.json()["code"] == "ALREADY_EXISTS"


def test_create_dir_bad_name(tmp_path) -> None:
    """非法目录名（含路径分隔符）-> 422 INVALID_NAME。"""
    app = create_app(task_manager=_manager())
    with TestClient(app) as client:
        resp = client.post("/v1/workspaces/dirs", json={"path": str(tmp_path), "name": "a/b"})
    assert resp.status_code == 422
    assert resp.json()["code"] == "INVALID_NAME"


def test_create_dir_missing_parent(tmp_path) -> None:
    """父目录不存在 -> 404 DIR_NOT_FOUND。"""
    app = create_app(task_manager=_manager())
    with TestClient(app) as client:
        resp = client.post(
            "/v1/workspaces/dirs", json={"path": str(tmp_path / "nope"), "name": "x"}
        )
    assert resp.status_code == 404


def test_task_in_path_workspace(tmp_path) -> None:
    """工作区 = 真实路径：任务创建/详情回显路径，且按路径过滤/聚合。"""
    ws = str(tmp_path / "project-a")
    (tmp_path / "project-a").mkdir()
    app = create_app(task_manager=_manager())
    with TestClient(app) as client:
        created = client.post("/v1/tasks", json={"task_input": "hi", "workspace_id": ws}).json()
        assert created["workspace_id"] == ws
        done = _wait_done(client, created["task_id"])
        assert done["workspace_id"] == ws
        only = client.get("/v1/tasks", params={"workspace": ws}).json()
        assert any(t["task_id"] == created["task_id"] for t in only)
        workspaces = client.get("/v1/workspaces").json()
        assert any(w["workspace_id"] == ws for w in workspaces)
