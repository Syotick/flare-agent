"""RAG 知识库测试（M3a：切块 / 嵌入 / 存储 / 管线 / 工具 / API / Agent 集成）。"""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import MemorySaver

from agent_runtime.app import create_app
from agent_runtime.tasks import TaskManager
from flare_common.errors import FlareError, ValidationError
from model_gateway.mock import MockModelProvider
from model_gateway.providers import ToolCall, ToolCallDecision
from rag.chunking import split_text
from rag.embedder import HashEmbedder
from rag.kb_tools import build_kb_search_tool
from rag.pipeline import KnowledgeBase
from rag.store import ChunkRecord, SqliteVectorStore
from tools_gateway.builtin import create_default_registry

TERMINAL = ("completed", "budget_exceeded", "failed")


# ---------- 切块 ----------


def test_split_text_empty() -> None:
    assert split_text("") == []
    assert split_text("   \n\n  ") == []


def test_split_text_respects_chunk_size() -> None:
    text = "\n".join(f"这是第{i}段内容，用来验证切块逻辑。" for i in range(30))
    chunks = split_text(text, chunk_size=120, overlap=20)
    assert chunks
    assert all(len(c) <= 120 for c in chunks)


def test_split_text_hard_splits_long_paragraph() -> None:
    long_para = "甲" * 300
    chunks = split_text(long_para, chunk_size=100, overlap=10)
    assert len(chunks) >= 3
    assert len(chunks[0]) == 100
    assert all(len(c) <= 100 for c in chunks)
    # 相邻块有重叠
    assert chunks[1].startswith(chunks[0][-10:])


# ---------- 嵌入 ----------


async def test_hash_embedder_deterministic_and_normalized() -> None:
    emb = HashEmbedder(dim=256)
    (v1,) = await emb.embed(["hello world"])
    (v2,) = await emb.embed(["hello world"])
    assert v1 == v2
    norm = sum(x * x for x in v1) ** 0.5
    assert abs(norm - 1.0) < 1e-6
    assert len(v1) == 256


async def test_hash_embedder_ranks_relevant_first() -> None:
    emb = HashEmbedder()
    query = "如何在阿里云上部署应用"
    related = "如何在阿里云上部署应用，参考部署指南与运维手册。"
    unrelated = "一份关于周末餐厅与美食的推荐清单。"
    q, r, u = await emb.embed([query, related, unrelated])
    score_r = sum(a * b for a, b in zip(q, r, strict=True))
    score_u = sum(a * b for a, b in zip(q, u, strict=True))
    assert score_r > score_u


async def test_hash_embedder_is_literal_not_semantic() -> None:
    """R6：暴露边界——HashEmbedder 是字面 n-gram 相似，不是语义。

    同义改写但零字面重合时得分应接近 0；只有逐字重合才高分。
    这让"语义检索 OK"的错觉现形：换真实嵌入模型（M3c/DashScope）才能谈语义召回。
    """
    emb = HashEmbedder()
    stored = "今天天气不错适合跑步"
    literal_q = "今天天气不错适合跑步"  # 逐字重合
    synonym_q = "going for a run in good weather"  # 语义相关但零字面重合
    s, lit, syn = await emb.embed([stored, literal_q, synonym_q])
    sim_lit = sum(a * b for a, b in zip(s, lit, strict=True))
    sim_syn = sum(a * b for a, b in zip(s, syn, strict=True))
    assert sim_lit > 0.9  # 逐字重合接近满分
    assert sim_syn < 0.5  # 无字面重合时显著偏低（暴露"非语义"边界）
    assert sim_lit > 5 * sim_syn


# ---------- 存储 ----------


async def test_sqlite_store_add_search_delete() -> None:
    store = SqliteVectorStore(":memory:")
    await store.add(
        "d1",
        "部署指南",
        [
            ChunkRecord(
                doc_id="d1", chunk_index=0, text="在阿里云上部署应用", vector=[1.0, 0.0, 0.0]
            ),
            ChunkRecord(doc_id="d1", chunk_index=1, text="餐厅推荐", vector=[0.0, 1.0, 0.0]),
        ],
    )
    hits = await store.search([0.9, 0.1, 0.0], k=1)
    assert hits and hits[0].doc_id == "d1" and hits[0].chunk_index == 0
    docs = await store.list_documents()
    assert len(docs) == 1 and docs[0].title == "部署指南"
    assert await store.delete("d1") is True
    assert await store.delete("d1") is False
    assert await store.list_documents() == []
    await store.close()


async def test_store_add_overwrites_stale_chunks() -> None:
    """R2：重复入库必须清除旧 chunk，不能残留仍可检索。"""
    store = SqliteVectorStore(":memory:")
    await store.add(
        "d1",
        "doc",
        [
            ChunkRecord(doc_id="d1", chunk_index=0, text="alpha", vector=[1.0, 0.0, 0.0]),
            ChunkRecord(doc_id="d1", chunk_index=1, text="beta", vector=[0.0, 1.0, 0.0]),
            ChunkRecord(doc_id="d1", chunk_index=2, text="gamma", vector=[0.0, 0.0, 1.0]),
        ],
    )
    # 重复入库仅 1 块 -> 旧 beta/gamma 必须被清除（唯一剩余 chunk 应为 alpha）
    await store.add(
        "d1", "doc", [ChunkRecord(doc_id="d1", chunk_index=0, text="alpha", vector=[1.0, 0.0, 0.0])]
    )
    hits_beta = await store.search([0.0, 1.0, 0.0], k=5)
    assert len(hits_beta) == 1 and hits_beta[0].text == "alpha"  # 旧 beta 已清除
    all_texts = [h.text for h in await store.search([0.0, 0.0, 1.0], k=5)]
    assert "beta" not in all_texts and "gamma" not in all_texts
    await store.close()


async def test_store_search_dimension_mismatch_raises() -> None:
    """R4：查询向量与存量维度不一致 -> 清晰报错（VectorDimError），而非 ValueError 崩掉。"""
    store = SqliteVectorStore(":memory:")
    await store.add(
        "d1", "doc", [ChunkRecord(doc_id="d1", chunk_index=0, text="a", vector=[1.0, 0.0])]
    )
    with pytest.raises(FlareError) as exc:
        await store.search([1.0, 0.0, 0.0, 0.0], k=1)
    assert exc.value.code == "VECTOR_DIM_MISMATCH"
    assert "维度" in exc.value.message
    await store.close()


# ---------- 管线 ----------


async def test_kb_ingest_search_delete() -> None:
    kb = KnowledgeBase()
    content = "在阿里云上部署应用，需要配置 ACK 集群与负载均衡。"
    res = await kb.ingest(title="部署指南", content=content)
    assert res.chunk_count == 1 and res.doc_id
    hits = await kb.search("怎么在阿里云上部署", k=3)
    assert hits and hits[0].title == "部署指南" and hits[0].score > 0.05
    assert await kb.delete(res.doc_id) is True
    assert await kb.search("部署") == []
    await kb.close()


# ---------- 工具 ----------


async def test_kb_search_tool_returns_citations() -> None:
    kb = KnowledgeBase()
    content = "所有服务部署到阿里云 ACK，容量告警阈值 70%。"
    await kb.ingest(title="运维手册", content=content)
    registry = create_default_registry()
    registry.register(build_kb_search_tool(kb))
    result = await registry.execute("kb_search", {"query": "部署到哪"})
    assert result.ok is True
    assert "运维手册" in result.content
    assert result.artifacts["hits"][0]["title"] == "运维手册"
    # 参数校验：缺少必填 query 会抛 ValidationError
    with pytest.raises(ValidationError):
        await registry.execute("kb_search", {})
    await kb.close()


# ---------- API ----------


def test_kb_api_ingest_search_delete() -> None:
    with TestClient(create_app()) as client:
        content = "POST /v1/kb/documents 用于入库，GET /v1/kb/search 用于检索。"
        resp = client.post("/v1/kb/documents", json={"title": "API手册", "content": content})
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["chunk_count"] >= 1 and body["doc_id"]

        hits = client.get("/v1/kb/search", params={"q": "怎么入库", "k": 3})
        assert hits.status_code == 200
        data = hits.json()
        assert data and data[0]["title"] == "API手册" and "score" in data[0]

        docs = client.get("/v1/kb/documents").json()
        assert any(d["doc_id"] == body["doc_id"] for d in docs)

        url = f"/v1/kb/documents/{body['doc_id']}"
        assert client.delete(url).status_code == 204
        assert client.delete(url).status_code == 404
        # 参数校验 422
        bad = client.post("/v1/kb/documents", json={"title": "", "content": "x"})
        assert bad.status_code == 422
        # R4：k 越界（>20）-> 422
        assert client.get("/v1/kb/search", params={"q": "x", "k": 999}).status_code == 422
        # R3：content 超上限 -> 422
        long_doc = "x" * 100_001
        assert (
            client.post(
                "/v1/kb/documents", json={"title": "too-long", "content": long_doc}
            ).status_code
            == 422
        )


# ---------- Agent 集成 ----------


class _KbSearchProvider(MockModelProvider):
    """mock 模型：先调一次 kb_search，再基于观察给结论。"""

    def __init__(self, query: str) -> None:
        self._query = query
        self._called = False

    def _decide(self, messages) -> ToolCallDecision:
        if self._called:
            last = messages[-1] if messages else None
            return ToolCallDecision(action="final", answer=f"完成: {last.content}")
        self._called = True
        tool = ToolCall(name="kb_search", args={"query": self._query})
        return ToolCallDecision(action="call_tool", tool=tool)


async def _mem_saver():
    return MemorySaver()


def test_agent_uses_kb_search_tool() -> None:
    """端到端：知识库入库 -> Agent 调 kb_search -> 基于观察给出带引用的结论。

    入库与任务执行都在 TestClient 的同一个事件循环里（aiosqlite 连接绑定 loop，
    跨 loop 共享会崩——这正是生产多 worker 前必须解耦存储的原因，M5 迁 Redis/DB）。
    """
    kb = KnowledgeBase()
    registry = create_default_registry()
    registry.register(build_kb_search_tool(kb))
    manager = TaskManager(
        registry=registry,
        llm=_KbSearchProvider("阿里云部署"),
        checkpointer_factory=_mem_saver,
    )
    with TestClient(create_app(task_manager=manager, knowledge_base=kb)) as client:
        content = "在阿里云上部署应用，需要配置 ACK 集群与负载均衡。"
        ing = client.post("/v1/kb/documents", json={"title": "部署指南", "content": content})
        assert ing.status_code == 201, ing.text

        resp = client.post("/v1/tasks", json={"task_input": "查一下部署知识", "max_steps": 3})
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
        assert "知识库" in output or "部署指南" in output


class _ToolAwareProvider(MockModelProvider):
    """R1：会读 system 提示的假模型——只有看到 kb_search 工具描述才决定调用。

    证明"工具 schema 注入 system 消息"这一前提成立：真实模型能据此自主调用。
    """

    def __init__(self, query: str) -> None:
        self._query = query
        self._called = False

    def _decide(self, messages) -> ToolCallDecision:
        system = next((m.content for m in messages if m.role == "system"), "")
        assert "kb_search" in system, "system 提示里必须暴露工具 schema（R1）"
        assert "在团队知识库中检索" in system
        if self._called:
            last = messages[-1] if messages else None
            return ToolCallDecision(action="final", answer=f"完成: {last.content}")
        self._called = True
        tool = ToolCall(name="kb_search", args={"query": self._query})
        return ToolCallDecision(action="call_tool", tool=tool)


def test_agent_autonomously_calls_kb_via_system_schema() -> None:
    """R1 端到端：模型基于 system 提示里的工具 schema 自主决定调 kb_search。"""
    kb = KnowledgeBase()
    registry = create_default_registry()
    registry.register(build_kb_search_tool(kb))
    manager = TaskManager(
        registry=registry,
        llm=_ToolAwareProvider("部署"),
        checkpointer_factory=_mem_saver,
    )
    with TestClient(create_app(task_manager=manager, knowledge_base=kb)) as client:
        content = "在阿里云上部署应用，需要配置 ACK 集群与负载均衡。"
        ing = client.post("/v1/kb/documents", json={"title": "部署指南", "content": content})
        assert ing.status_code == 201, ing.text

        resp = client.post("/v1/tasks", json={"task_input": "查一下部署知识", "max_steps": 3})
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
        assert "知识库" in output or "部署指南" in output
