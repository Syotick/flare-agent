"""分层记忆测试（M3b-FR-4：事实库 / 向量记忆 / 上下文工程 / 工具 / API / Agent 注入）。"""

from __future__ import annotations

import time

from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import MemorySaver

from agent_runtime.app import create_app
from agent_runtime.tasks import TaskManager
from memory.context import assemble, summarize, truncate
from memory.mem_tools import build_memory_tools
from memory.memory import MemoryManager
from model_gateway.mock import MockModelProvider
from model_gateway.providers import ToolCallDecision
from tools_gateway.builtin import create_default_registry

TERMINAL = ("completed", "budget_exceeded", "failed")


# ---------- 上下文工程（F4.3） ----------


def test_summarize_cuts_at_sentence_boundary() -> None:
    s = summarize("第一句话很长的内容。" + "第二句。" * 30, max_chars=20)
    assert s.endswith("…")
    assert len(s) <= 20


def test_truncate_shortens() -> None:
    assert truncate("abcd", 2) == "a…"
    assert truncate("ab", 2) == "ab"


def test_assemble_respects_budget() -> None:
    facts = [("k", "x" * 300)] * 5
    hits = [("src", "y" * 300, 0.9)] * 5
    block = assemble(facts=facts, hits=hits, budget_chars=200)
    assert len(block) <= 200


def test_assemble_empty() -> None:
    assert assemble() == ""


# ---------- 事实库（项目长期记忆） ----------


async def test_facts_crud_and_project_scope() -> None:
    mem = MemoryManager()
    await mem.remember_fact("a", "1")
    assert (await mem.get_fact("a")).value == "1"
    await mem.remember_fact("a", "2")  # upsert
    assert (await mem.get_fact("a")).value == "2"
    assert len(await mem.list_facts()) == 1
    await mem.remember_fact("b", "3", project_id="other")
    assert len(await mem.list_facts()) == 1  # 默认项目隔离
    assert len(await mem.list_facts(project_id="other")) == 1
    assert await mem.forget_fact("a") is True
    assert await mem.forget_fact("a") is False
    await mem.close()


# ---------- 向量记忆（语义召回） ----------


async def test_memory_vector_recall() -> None:
    mem = MemoryManager()
    await mem.remember_note("用户偏好使用 Vim 编辑代码")
    await mem.remember_note("周末想去吃火锅和烧烤")
    hits = await mem.search_memory("用户喜欢什么编辑器", k=2)
    assert hits
    texts = [h.text for h in hits]
    assert any("Vim" in t for t in texts)
    await mem.close()


async def test_build_context_combines_layers() -> None:
    mem = MemoryManager()
    await mem.remember_fact("project", "Flare Agent")
    await mem.remember_note("部署在阿里云 ACK 集群")
    block = await mem.build_context(query="部署")
    assert "[项目记忆]" in block and "Flare Agent" in block
    assert "[向量记忆]" in block
    await mem.close()


# ---------- 工具 ----------


async def test_mem_tools_via_registry() -> None:
    mem = MemoryManager()
    registry = create_default_registry()
    for tool in build_memory_tools(mem):
        registry.register(tool)
    r1 = await registry.execute("mem_set", {"key": "nickname", "value": "用户叫小明"})
    assert r1.ok and "小明" in r1.content
    r2 = await registry.execute("mem_recall", {"query": "我的昵称"})
    assert "小明" in r2.content
    await mem.close()


# ---------- API ----------


def test_memory_api() -> None:
    with TestClient(create_app()) as client:
        put = client.put("/v1/memory/facts/nickname", json={"value": "小明"})
        assert put.status_code == 200 and put.json()["value"] == "小明"
        assert client.get("/v1/memory/facts/nickname").json()["key"] == "nickname"
        assert any(f["key"] == "nickname" for f in client.get("/v1/memory/facts").json())

        note = client.post("/v1/memory/notes", json={"text": "部署在阿里云 ACK"})
        assert note.status_code == 200 and note.json()["note_id"]

        hits = client.post("/v1/memory/search", json={"q": "部署", "k": 3})
        assert hits.status_code == 200 and hits.json()["hits"]

        ctx = client.get("/v1/memory/context", params={"q": "部署"})
        assert "[项目记忆]" in ctx.json()["block"]

        assert client.delete("/v1/memory/facts/nickname").status_code == 204
        assert client.get("/v1/memory/facts/nickname").status_code == 404


# ---------- Agent 集成：上下文注入（F4.3） ----------


class _EchoUserProvider(MockModelProvider):
    """把收到的首个 user 消息原样作为最终答案，便于断言上下文注入了记忆。"""

    def _decide(self, messages) -> ToolCallDecision:
        last_user = next((m.content for m in reversed(messages) if m.role == "user"), "")
        return ToolCallDecision(action="final", answer=last_user)


async def _mem_saver():
    return MemorySaver()


def test_memory_context_injected_into_task() -> None:
    """端到端：事实入库 -> 任务开始时按 task_input 召回 -> 上下文注入首个 user 消息。"""
    mem = MemoryManager()
    registry = create_default_registry()
    for tool in build_memory_tools(mem):
        registry.register(tool)
    manager = TaskManager(
        registry=registry,
        llm=_EchoUserProvider(),
        checkpointer_factory=_mem_saver,
        memory=mem,
    )
    with TestClient(create_app(task_manager=manager, memory=mem)) as client:
        put = client.put("/v1/memory/facts/nickname", json={"value": "用户叫小明"})
        assert put.status_code == 200, put.text

        resp = client.post("/v1/tasks", json={"task_input": "介绍一下我", "max_steps": 2})
        assert resp.status_code == 202
        task_id = resp.json()["task_id"]

        deadline = time.time() + 5.0
        body = None
        while time.time() < deadline:
            body = client.get(f"/v1/tasks/{task_id}").json()
            if body["status"] in TERMINAL:
                break
            time.sleep(0.02)
        assert body is not None and body["status"] == "completed", body
        output = (body.get("result") or {}).get("output") or ""
        assert "[项目记忆]" in output
        assert "小明" in output
