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


async def test_build_context_recent_layer() -> None:
    """M1：recent（短期对话层）真正参与上下文工程。"""
    mem = MemoryManager()
    await mem.remember_fact("project", "Flare Agent")
    block = await mem.build_context(recent=["user: 我叫小明", "assistant: 好的小明"], query="")
    assert "[近期对话]" in block
    assert "我叫小明" in block
    assert "[项目记忆]" in block
    await mem.close()


async def test_mem_recall_is_budgeted() -> None:
    """M2：mem_recall 不再全量倾倒——按相关度排序 + 封顶条数。"""
    mem = MemoryManager()
    registry = create_default_registry()
    for tool in build_memory_tools(mem):
        registry.register(tool)
    for i in range(10):  # 造 10 条无关事实 + 1 条相关事实
        await mem.remember_fact(f"f{i}", f"第 {i} 条无关事实内容")
    await mem.remember_fact("deploy", "生产环境部署到阿里云 ACK")
    r = await registry.execute("mem_recall", {"query": "部署", "k": 3})
    assert r.ok
    assert "deploy" in r.content  # 相关事实在前
    # 封顶：k+2=5 条，11 条事实不可能全量倾倒；最旧的 f0 被挤出
    assert len(r.artifacts["facts"]) <= 5
    assert r.artifacts["facts"][0] == "deploy"
    assert "第 0 条无关事实内容" not in r.content
    await mem.close()


async def test_note_source_is_readable() -> None:
    """M3：向量记忆溯源可读（文本前缀 + 短 id），而非 memory:<nid>。"""
    mem = MemoryManager()
    nid = await mem.remember_note("用户偏好使用 Vim 编辑代码")
    hits = await mem.search_memory("编辑器", k=2)
    assert hits
    src = hits[0].source
    assert not src.startswith("memory:")
    assert "Vim" in src and nid[:6] in src
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


def test_recent_layer_injected_on_resumed_thread() -> None:
    """M1 端到端：同一 thread 续聊 -> 第二任务注入该线程近期对话（短期对话层真正接线）。

    共享同一 checkpointer：任务 1 跑完后线程有历史，任务 2 的 build_context 取到 recent，
    [近期对话] 会出现在注入上下文里。
    """
    mem = MemoryManager()
    registry = create_default_registry()
    for tool in build_memory_tools(mem):
        registry.register(tool)
    saver = MemorySaver()

    async def _shared_saver():
        return saver

    manager = TaskManager(
        registry=registry,
        llm=_EchoUserProvider(),
        checkpointer_factory=_shared_saver,
        memory=mem,
    )
    with TestClient(create_app(task_manager=manager, memory=mem)) as client:
        put = client.put("/v1/memory/facts/nickname", json={"value": "用户叫小明"})
        assert put.status_code == 200, put.text

        # 任务 1：新线程，跑出对话历史
        r1 = client.post(
            "/v1/tasks", json={"task_input": "我叫小明", "max_steps": 5, "thread_id": "s1"}
        )
        assert r1.status_code == 202
        id1 = r1.json()["task_id"]
        deadline = time.time() + 5.0
        while time.time() < deadline:
            b1 = client.get(f"/v1/tasks/{id1}").json()
            if b1["status"] in TERMINAL:
                break
            time.sleep(0.02)
        assert b1["status"] == "completed", b1

        # 任务 2：同一 thread 续聊 -> 注入近期对话
        r2 = client.post(
            "/v1/tasks", json={"task_input": "我昨天说了什么", "max_steps": 5, "thread_id": "s1"}
        )
        assert r2.status_code == 202
        id2 = r2.json()["task_id"]
        deadline = time.time() + 5.0
        while time.time() < deadline:
            b2 = client.get(f"/v1/tasks/{id2}").json()
            if b2["status"] in TERMINAL:
                break
            time.sleep(0.02)
        assert b2["status"] == "completed", b2
        out2 = (b2.get("result") or {}).get("output") or ""
        assert "[近期对话]" in out2  # 短期对话层真实注入
        assert "我叫小明" in out2  # 上一任务的对话内容在 recent 里
