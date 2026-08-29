"""F1.3 人机协作审批 + F2.4 工具权限分级 + TOFU + 多实例后端 测试。

覆盖：权限打标 / 审批策略 / 管理器（登记-等待-决策-超时）/ 图内 interrupt 审批门 /
      TaskManager 任务端到端（awaiting_approval → 决策放行/拒绝续跑）/ TOFU（首用信任，
      免 interrupt 直行）/ Redis 后端（跨节点轮询唤醒/超时/索引）/ REST 契约 / create_app 挂载。
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
from agent_runtime.approval import (
    ApprovalManager,
    ApprovalPolicy,
    ApprovalRequest,
    RedisApprovalBackend,
)
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

    async def stream(self, messages, *, model=None, temperature=None, tools: list[dict] | None = None):
        resp = await self.chat(messages, model=model, temperature=temperature)
        yield resp.content


class DoubleSandboxProvider:
    """确定性 mock：连续要求执行 sandbox_run 两次（验证 TOFU 第二次免 interrupt）。"""

    model = "double-sandbox"

    def __init__(self) -> None:
        self._executions = 0

    async def chat(self, messages, *, model=None, temperature=None, max_tokens=None, tools=None):
        last = messages[-1] if messages else None
        if last is not None and last.role == "tool":
            self._executions += 1
            if self._executions == 1:  # 第一次工具观察后 -> 再调一次（触发 TOFU 判定）
                return LLMResponse(
                    content=json.dumps(
                        {
                            "action": "call_tool",
                            "tool": {"name": "sandbox_run", "args": {"code": "print(2)"}},
                        }
                    ),
                    model=self.model,
                    usage=LLMUsage(),
                )
            return LLMResponse(
                content=json.dumps({"action": "final", "answer": f"完成: {last.content}"}),
                model=self.model,
                usage=LLMUsage(),
            )
        return LLMResponse(
            content=json.dumps(
                {
                    "action": "call_tool",
                    "tool": {"name": "sandbox_run", "args": {"code": "print(1)"}},
                }
            ),
            model=self.model,
            usage=LLMUsage(),
        )

    async def stream(self, messages, *, model=None, temperature=None, tools: list[dict] | None = None):
        resp = await self.chat(messages, model=model, temperature=temperature)
        yield resp.content


class FakeRedis:
    """进程内 redis 桩（零依赖）：实现 RedisApprovalBackend 用到的命令子集。"""

    def __init__(self) -> None:
        self._h: dict[str, dict[str, str]] = {}
        self._s: dict[str, set[str]] = {}
        self._z: dict[str, dict[str, float]] = {}
        self._closed = False

    async def ping(self) -> bool:
        return True

    async def aclose(self) -> None:
        self._closed = True

    async def hset(self, name: str, field: str, value: str) -> None:
        self._h.setdefault(name, {})[field] = value

    async def hget(self, name: str, field: str):
        return self._h.get(name, {}).get(field)

    async def sadd(self, name: str, *members: str) -> None:
        self._s.setdefault(name, set()).update(members)

    async def srem(self, name: str, *members: str) -> None:
        s = self._s.get(name)
        if s:
            for m in members:
                s.discard(m)

    async def smembers(self, name: str) -> set[str]:
        return set(self._s.get(name, set()))

    async def sismember(self, name: str, member: str) -> bool:
        return member in self._s.get(name, set())

    async def zadd(self, name: str, mapping: dict[str, float]) -> None:
        self._z.setdefault(name, {}).update(mapping)

    async def zrange(self, name: str, start: int, end: int) -> list[str]:
        items = sorted(self._z.get(name, {}).items(), key=lambda kv: kv[1])
        return [k for k, _ in items] if end == -1 else [k for k, _ in items[start : end + 1]]


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
    req = await m.register("task1", "sandbox_run", {"code": "x"}, permission=PERMISSION_DESTRUCTIVE)
    assert req.status == "pending" and req.approval_id

    async def decider():
        await asyncio.sleep(0.05)
        await m.decide(req.approval_id, approved=True, decided_by="admin", reason="ok")

    d = asyncio.create_task(decider())
    decision = await m.wait(req.approval_id)
    assert decision == {"approved": True, "reason": "ok"}
    await d
    assert req.status == "approved" and req.decided_by == "admin"
    with pytest.raises(ValueError):
        await m.decide(req.approval_id, approved=False)  # 重复决策拒绝


async def test_approval_wait_timeout_auto_rejects() -> None:
    m = ApprovalManager(timeout=0.2)
    req = await m.register("task1", "sandbox_run", {})
    decision = await m.wait(req.approval_id)
    assert decision["approved"] is False
    assert "超时" in decision["reason"]
    assert req.status == "timed_out"


# ---------- TOFU（首用信任） ----------


async def test_tofu_trusts_scope_after_approve() -> None:
    m = ApprovalManager(ApprovalPolicy(), timeout=5.0)
    tool = _reg().get("sandbox_run")
    assert await m.requires_approval(tool, scope="th-1") is True
    req = await m.register("t1", "sandbox_run", {}, permission=PERMISSION_DESTRUCTIVE, scope="th-1")
    await m.decide(req.approval_id, approved=True, decided_by="admin")
    assert await m.requires_approval(tool, scope="th-1") is False  # TOFU 放行
    assert await m.requires_approval(tool, scope="th-2") is True  # 其他作用域不受影响
    assert await m.requires_approval(tool) is True  # 无作用域 -> 不信任


async def test_tofu_disabled_still_requires() -> None:
    m = ApprovalManager(ApprovalPolicy(), timeout=5.0, tofu_enabled=False)
    tool = _reg().get("sandbox_run")
    req = await m.register("t1", "sandbox_run", {}, permission=PERMISSION_DESTRUCTIVE, scope="s")
    await m.decide(req.approval_id, approved=True)
    assert await m.requires_approval(tool, scope="s") is True


async def test_tofu_reject_does_not_trust() -> None:
    m = ApprovalManager(ApprovalPolicy(), timeout=5.0)
    tool = _reg().get("sandbox_run")
    req = await m.register("t1", "sandbox_run", {}, permission=PERMISSION_DESTRUCTIVE, scope="th-1")
    await m.decide(req.approval_id, approved=False, decided_by="admin", reason="危险")
    assert await m.requires_approval(tool, scope="th-1") is True


def test_scope_for_resolution() -> None:
    assert ApprovalManager(tofu_scope="thread").scope_for("th1", "tenant-x") == "th1"
    assert ApprovalManager(tofu_scope="tenant").scope_for("th1", "tenant-x") == "tenant-x"
    assert ApprovalManager(tofu_scope="off").scope_for("th1", "tenant-x") is None
    assert ApprovalManager(tofu_enabled=False).scope_for("th1", "tenant-x") is None
    with pytest.raises(ValueError):
        ApprovalManager(tofu_scope="nope")


# ---------- Redis 后端（多实例） ----------


async def test_redis_backend_cross_instance_decision() -> None:
    fake = FakeRedis()
    inst_a = RedisApprovalBackend(fake, poll_interval=0.02)  # 实例 A：登记并等待
    inst_b = RedisApprovalBackend(fake, poll_interval=0.02)  # 实例 B：决策
    req = ApprovalRequest(
        approval_id="r1",
        task_id="t1",
        tool_name="sandbox_run",
        args={"code": "x"},
        permission=PERMISSION_DESTRUCTIVE,
        scope="th-1",
    )
    await inst_a.save(req)

    async def waiter():
        return await inst_a.wait("r1", timeout=2.0)

    w = asyncio.create_task(waiter())
    await asyncio.sleep(0.05)
    decided = await inst_b.decide("r1", approved=True, decided_by="admin")
    assert decided.status == "approved"
    got = await w
    assert got.status == "approved" and got.decided_by == "admin"
    # 信任集跨节点共享：实例 A 记录，实例 B 可见（manager 在决策获批后经后端 record_trust）
    await inst_a.record_trust("th-1", "sandbox_run")
    assert await inst_b.is_trusted("th-1", "sandbox_run") is True


async def test_redis_backend_timeout() -> None:
    fake = FakeRedis()
    inst = RedisApprovalBackend(fake, poll_interval=0.02)
    req = ApprovalRequest(
        approval_id="r2",
        task_id="t1",
        tool_name="sandbox_run",
        args={},
        permission=PERMISSION_DESTRUCTIVE,
        scope="",
    )
    await inst.save(req)
    got = await inst.wait("r2", timeout=0.2)
    assert got.status == "timed_out"
    assert "超时" in got.reason


async def test_redis_backend_pending_and_list() -> None:
    fake = FakeRedis()
    inst = RedisApprovalBackend(fake)
    for i in range(2):
        req = ApprovalRequest(
            approval_id=f"r{i}",
            task_id="t1",
            tool_name="sandbox_run",
            args={},
            permission=PERMISSION_DESTRUCTIVE,
            scope="s",
        )
        await inst.save(req)
    assert len(await inst.pending()) == 2
    await inst.decide("r0", approved=True)
    pend = await inst.pending()
    assert [p.approval_id for p in pend] == ["r1"]
    assert len(await inst.list()) == 2


async def test_manager_over_redis_backend_e2e() -> None:
    fake = FakeRedis()
    m = ApprovalManager(
        ApprovalPolicy(),
        timeout=2.0,
        backend=RedisApprovalBackend(fake, poll_interval=0.02),
        tofu_enabled=True,
        tofu_scope="thread",
    )
    tool = _reg().get("sandbox_run")
    req = await m.register(
        "t1", "sandbox_run", {"code": "x"}, permission=PERMISSION_DESTRUCTIVE, scope="th-1"
    )
    assert (await m.pending())[0].approval_id == req.approval_id

    async def waiter():
        return await m.wait(req.approval_id)

    w = asyncio.create_task(waiter())
    await asyncio.sleep(0.05)
    await m.decide(req.approval_id, approved=True, decided_by="admin")
    decision = await w
    assert decision == {"approved": True, "reason": ""}
    assert await m.requires_approval(tool, scope="th-1") is False  # TOFU 经 Redis 生效


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


async def test_graph_tofu_skips_second_interrupt() -> None:
    """TOFU：同作用域首次获批后，第二次调用免 interrupt 直行。"""
    manager = ApprovalManager(ApprovalPolicy(), timeout=5.0)
    agent = build_react_agent(
        DoubleSandboxProvider(),
        _reg(),
        checkpointer=MemorySaver(),
        approval=manager,
        approval_scope="g-tofu",
    )
    cfg = {"configurable": {"thread_id": "gtofu"}}
    interrupts = 0
    pending_input: object = {"task_input": "run twice"}
    while True:
        hit = False
        async for update in agent.astream(pending_input, cfg, stream_mode="updates"):
            if "__interrupt__" in update:
                interrupts += 1
                payload = update["__interrupt__"][0].value
                req = await manager.register(
                    "t",
                    payload["tool"],
                    payload["args"],
                    permission=payload["permission"],
                    description=payload["description"],
                    scope="g-tofu",
                )
                await manager.decide(req.approval_id, approved=True, decided_by="tester")
                pending_input = Command(resume={"approved": True})
                hit = True
                break
        if not hit:
            break
    final = await agent.aget_state(cfg)
    assert interrupts == 1  # 第二次 TOFU 放行，不再 interrupt
    assert final.values["status"] == "completed"
    assert final.values["step_count"] == 2  # 两次沙箱执行都发生了（第二次未中断）
    tool_obs = [
        m.content
        for m in final.values["messages"]
        if getattr(m, "role", None) == "tool" and "sandbox-output" in getattr(m, "content", "")
    ]
    assert len(tool_obs) == 2


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
    req = (await manager.approval.pending())[0]
    assert req.tool_name == "sandbox_run" and req.task_id == task.task_id
    await manager.approval.decide(req.approval_id, approved=True, decided_by="tester")
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
    req = (await manager.approval.pending())[0]
    await manager.approval.decide(
        req.approval_id, approved=False, decided_by="tester", reason="危险"
    )
    deadline = time.time() + 5
    while not task.done and time.time() < deadline:
        await asyncio.sleep(0.02)
    assert task.status == "completed"
    assert "拒绝" in (task.result or {}).get("output", "")


async def test_task_tofu_second_task_same_thread_skips_approval() -> None:
    """TOFU：同一线程第二次任务（续聊）执行 destructive 工具不再审批。"""
    manager = TaskManager(
        registry=_reg(),
        llm=DoubleSandboxProvider(),
        checkpointer_factory=_mem,
        approval=ApprovalManager(ApprovalPolicy(), timeout=10.0, tofu_scope="thread"),
    )
    task = await manager.create("run twice", thread_id="same-thread")
    await _wait_status(task, "awaiting_approval")
    req = (await manager.approval.pending())[0]
    await manager.approval.decide(req.approval_id, approved=True, decided_by="tester")
    deadline = time.time() + 5
    while not task.done and time.time() < deadline:
        await asyncio.sleep(0.02)
    assert task.status == "completed"
    assert (task.result or {}).get("step_count") == 2  # 两次沙箱执行（第二次未中断）
    assert [ev["type"] for ev in task.events].count("approval") == 1  # 只有首次需要审批


# ---------- REST 契约 ----------


def test_approval_router_flow() -> None:
    manager = ApprovalManager(timeout=10.0)
    app = FastAPI()
    app.include_router(build_approval_router(manager))
    req = asyncio.run(
        manager.register("task1", "sandbox_run", {"code": "x"}, permission=PERMISSION_DESTRUCTIVE)
    )
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
