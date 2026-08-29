"""F1.3 人机协作审批 + F2.4 工具权限分级 测试。

覆盖：权限打标 / 审批策略 / 管理器（登记-等待-决策-超时）/ 图内 interrupt 审批门 /
      TaskManager 任务端到端（awaiting_approval → 决策放行/拒绝续跑）/ REST 契约 / create_app 挂载。
"""

from __future__ import annotations

import asyncio
import json
import time
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from agent_runtime.app import create_app
from agent_runtime.approval import ApprovalManager, ApprovalPolicy
from agent_runtime.graph import build_react_agent
from agent_runtime.routes.approval import build_approval_router
from agent_runtime.tasks import TaskManager
from flare_common.config import Settings
from model_gateway.providers import LLMResponse, LLMUsage
from tools_gateway.builtin import create_default_registry
from tools_gateway.registry import (
    PERMISSION_DESTRUCTIVE,
    PERMISSION_READ,
    PERMISSION_WRITE,
    Tool,
    ToolResult,
)


class FakeSandbox:
    """沙箱桩：确定性返回输出，验证审批放行后真实执行路径。"""

    async def run(self, code: str, language: str = "python", stdin: str | None = None):
        return SimpleNamespace(
            stdout="sandbox-output",
            stderr="",
            ok=True,
            timed_out=False,
            exit_code=0,
            duration_s=0.1,
        )


class SandboxCallProvider:
    """确定性 mock：先要求执行 sandbox_run，观察结果后收尾。"""

    model = "sandbox-call"

    async def chat(self, messages, *, model=None, temperature=None, max_tokens=None, tools=None):
        last = messages[-1] if messages else None
        if last is not None and last.role == "tool":
            content = json.dumps({"action": "final", "answer": f"完成: {last.content}"})
        else:
            content = json.dumps(
                {
                    "action": "call_tool",
                    "tool": {"name": "sandbox_run", "args": {"code": "print(1)"}},
                }
            )
        return LLMResponse(content=content, model=self.model, usage=LLMUsage())

    async def stream(self, messages, *, model=None, temperature=None):
        resp = await self.chat(messages, model=model, temperature=temperature)
        yield resp.content


def _reg() -> object:
    return create_default_registry(sandbox=FakeSandbox())


async def _mem():
    return MemorySaver()


# ---------- F2.4 权限打标与策略 ----------


def test_permission_tags() -> None:
    reg = _reg()
    assert reg.get("echo").permission == PERMISSION_READ
    assert reg.get("sandbox_run").permission == PERMISSION_DESTRUCTIVE


def test_policy_default_destructive_requires_approval() -> None:
    reg = _reg()
    policy = ApprovalPolicy()
    assert policy.requires_approval(reg.get("sandbox_run")) is True
    assert policy.requires_approval(reg.get("echo")) is False


def test_policy_strict_level_and_extra_tools() -> None:
    write_tool = Tool(
        name="w",
        description="",
        parameters={"type": "object"},
        func=lambda **kw: ToolResult(ok=True),
        permission=PERMISSION_WRITE,
    )
    strict = ApprovalPolicy(require_level=PERMISSION_WRITE)
    assert strict.requires_approval(write_tool) is True
    extra = ApprovalPolicy(extra_tools={"echo"})
    reg = _reg()
    assert extra.requires_approval(reg.get("echo")) is True
    with pytest.raises(ValueError):
        ApprovalPolicy(require_level="nope")


# ---------- 审批管理器 ----------


async def test_approval_register_wait_decide() -> None:
    m = ApprovalManager(timeout=5.0)
    req = m.register("task1", "sandbox_run", {"code": "x"}, permission=PERMISSION_DESTRUCTIVE)
    assert req.status == "pending" and req.approval_id

    async def decider():
        await asyncio.sleep(0.05)
        m.decide(req.approval_id, approved=True, decided_by="admin", reason="ok")

    d = asyncio.create_task(decider())
    decision = await m.wait(req.approval_id)
    assert decision == {"approved": True, "reason": "ok"}
    await d
    assert req.status == "approved" and req.decided_by == "admin"
    with pytest.raises(ValueError):
        m.decide(req.approval_id, approved=False)  # 重复决策拒绝


async def test_approval_wait_timeout_auto_rejects() -> None:
    m = ApprovalManager(timeout=0.2)
    req = m.register("task1", "sandbox_run", {})
    decision = await m.wait(req.approval_id)
    assert decision["approved"] is False
    assert "超时" in decision["reason"]
    assert req.status == "timed_out"


# ---------- 图内审批门（interrupt） ----------


async def test_graph_interrupts_then_approve_executes() -> None:
    manager = ApprovalManager(timeout=5.0)
    agent = build_react_agent(
        SandboxCallProvider(), _reg(), checkpointer=MemorySaver(), approval=manager
    )
    cfg = {"configurable": {"thread_id": "g1"}}
    payload = None
    async for update in agent.astream({"task_input": "run"}, cfg, stream_mode="updates"):
        if "__interrupt__" in update:
            payload = update["__interrupt__"][0].value
    assert payload is not None
    assert payload["type"] == "approval" and payload["tool"] == "sandbox_run"
    assert payload["permission"] == PERMISSION_DESTRUCTIVE
    async for _ in agent.astream(Command(resume={"approved": True}), cfg, stream_mode="updates"):
        pass
    final = await agent.aget_state(cfg)
    assert final.values["status"] == "completed"
    assert "sandbox-output" in final.values["output"]


async def test_graph_reject_observes_refusal() -> None:
    manager = ApprovalManager(timeout=5.0)
    agent = build_react_agent(
        SandboxCallProvider(), _reg(), checkpointer=MemorySaver(), approval=manager
    )
    cfg = {"configurable": {"thread_id": "g2"}}
    async for update in agent.astream({"task_input": "run"}, cfg, stream_mode="updates"):
        if "__interrupt__" in update:
            payload = update["__interrupt__"][0].value
    assert payload["tool"] == "sandbox_run"
    async for _ in agent.astream(
        Command(resume={"approved": False, "reason": "危险"}), cfg, stream_mode="updates"
    ):
        pass
    final = await agent.aget_state(cfg)
    assert final.values["status"] == "completed"
    assert "拒绝" in final.values["output"]


async def test_graph_without_approval_gate_runs_unchanged() -> None:
    """approval=None（默认）：无审批门，行为与之前一致。"""
    agent = build_react_agent(SandboxCallProvider(), _reg(), checkpointer=MemorySaver())
    cfg = {"configurable": {"thread_id": "g3"}}
    result = await agent.ainvoke({"task_input": "run"}, cfg)
    assert result["status"] == "completed"
    assert "sandbox-output" in result["output"]


# ---------- TaskManager 端到端 ----------


async def _wait_status(task, status, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if task.status == status:
            return
        await asyncio.sleep(0.02)
    raise AssertionError(f"task 未到 {status}: {task.status}")


async def test_task_awaiting_approval_then_approve_completes() -> None:
    manager = TaskManager(
        registry=_reg(),
        llm=SandboxCallProvider(),
        checkpointer_factory=_mem,
        approval=ApprovalManager(ApprovalPolicy(), timeout=10.0),
    )
    task = await manager.create("run it")
    await _wait_status(task, "awaiting_approval")
    assert manager.approval is not None
    req = manager.approval.pending()[0]
    assert req.tool_name == "sandbox_run" and req.task_id == task.task_id
    manager.approval.decide(req.approval_id, approved=True, decided_by="tester")
    deadline = time.time() + 5
    while not task.done and time.time() < deadline:
        await asyncio.sleep(0.02)
    assert task.status == "completed"
    assert "sandbox-output" in (task.result or {}).get("output", "")
    # SSE 事件含 approval + approval_decision
    types = [ev["type"] for ev in task.events]
    assert "approval" in types and "approval_decision" in types


async def test_task_reject_then_continues() -> None:
    manager = TaskManager(
        registry=_reg(),
        llm=SandboxCallProvider(),
        checkpointer_factory=_mem,
        approval=ApprovalManager(ApprovalPolicy(), timeout=10.0),
    )
    task = await manager.create("run it")
    await _wait_status(task, "awaiting_approval")
    req = manager.approval.pending()[0]
    manager.approval.decide(req.approval_id, approved=False, decided_by="tester", reason="危险")
    deadline = time.time() + 5
    while not task.done and time.time() < deadline:
        await asyncio.sleep(0.02)
    assert task.status == "completed"
    assert "拒绝" in (task.result or {}).get("output", "")


# ---------- REST 契约 ----------


def test_approval_router_flow() -> None:
    manager = ApprovalManager(timeout=10.0)
    app = FastAPI()
    app.include_router(build_approval_router(manager))
    req = manager.register("task1", "sandbox_run", {"code": "x"}, permission=PERMISSION_DESTRUCTIVE)
    with TestClient(app) as client:
        lst = client.get("/v1/approvals?pending_only=true").json()
        assert len(lst) == 1 and lst[0]["approval_id"] == req.approval_id
        detail = client.get(f"/v1/approvals/{req.approval_id}").json()
        assert detail["status"] == "pending" and detail["tool_name"] == "sandbox_run"
        resp = client.post(
            f"/v1/approvals/{req.approval_id}/decide",
            json={"approved": True, "decided_by": "admin", "reason": "ok"},
        )
        assert resp.status_code == 200 and resp.json()["status"] == "approved"
        assert client.get("/v1/approvals?pending_only=true").json() == []
        dup = client.post(f"/v1/approvals/{req.approval_id}/decide", json={"approved": False})
        assert dup.status_code == 409
        assert client.get("/v1/approvals/nope").status_code == 404
        assert client.post("/v1/approvals/nope/decide", json={"approved": True}).status_code == 404


def test_approval_mounted_in_create_app() -> None:
    app = create_app(settings=Settings(env="test"))
    with TestClient(app) as client:
        assert client.get("/v1/approvals").status_code == 200
        assert client.get("/v1/approvals?pending_only=true").json() == []
