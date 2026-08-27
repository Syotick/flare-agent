"""RAG 评测测试（M3c）：确定性指标 / 混合检索 / 重排 / 策略对比 / RAGAS 代理判定 / API。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from agent_runtime.app import create_app
from flare_common.errors import ValidationError
from model_gateway.mock import MockModelProvider
from rag.eval import builtin_dataset, run_retrieval_eval
from rag.eval.metrics import (
    aggregate,
    hit_at_k,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)
from rag.eval.ragas import (
    CoverageProxyJudge,
    LLMJudge,
    RagJudgeUnavailableError,
    run_ragas,
)
from rag.hybrid import KeywordIndex, rrf
from rag.pipeline import KnowledgeBase
from rag.rerank import CoverageReranker, DashScopeReranker, RerankUnavailableError
from rag.store import ChunkRecord, SearchHit, SqliteVectorStore

# ---------- 确定性指标 ----------


def test_metrics_hand_computed() -> None:
    hits = ["d1", "d2", "d3", "d4", "d5"]
    rel = {"d2", "d4"}
    assert recall_at_k(hits, rel, 5) == pytest.approx(1.0)
    assert recall_at_k(hits, rel, 3) == pytest.approx(0.5)  # 只有 d2 在 top3
    assert precision_at_k(hits, rel, 3) == pytest.approx(1 / 3)
    assert hit_at_k(hits, rel, 3) == 1.0
    assert hit_at_k(hits, {"d9"}, 3) == 0.0
    assert reciprocal_rank(hits, rel) == pytest.approx(0.5)  # d2 在第 2 位
    # NDCG@3：DCG = 1/log2(3)（d2），IDCG = 1/log2(2)+1/log2(3)
    assert ndcg_at_k(hits, rel, 3) == pytest.approx((1 / 1.58496) / (1 + 1 / 1.58496), rel=1e-3)


def test_metrics_miss() -> None:
    hits = ["a", "b", "c"]
    assert recall_at_k(hits, {"z"}, 3) == 0.0
    assert precision_at_k(hits, {"z"}, 3) == 0.0
    assert reciprocal_rank(hits, {"z"}) == 0.0
    assert ndcg_at_k(hits, {"z"}, 3) == 0.0


def test_aggregate_averages() -> None:
    rows = [
        {"recall@k": 1.0, "precision@k": 0.4, "hit_rate": 1.0, "mrr": 1.0, "ndcg@k": 1.0},
        {"recall@k": 0.0, "precision@k": 0.0, "hit_rate": 0.0, "mrr": 0.0, "ndcg@k": 0.0},
    ]
    agg = aggregate(rows)
    assert agg["recall@k"] == 0.5
    assert agg["hit_rate"] == 0.5
    assert agg["mrr"] == 0.5
    assert aggregate([]) == {
        "recall@k": 0.0,
        "precision@k": 0.0,
        "hit_rate": 0.0,
        "mrr": 0.0,
        "ndcg@k": 0.0,
    }


# ---------- 混合检索 ----------


def test_keyword_index_bm25_ranks_relevant_first() -> None:
    chunks = [
        ChunkRecord(doc_id="a", chunk_index=0, text="ACK 集群容量告警阈值是 70%", vector=[]),
        ChunkRecord(doc_id="b", chunk_index=0, text="前端页面使用 React 与 Tailwind", vector=[]),
    ]
    idx = KeywordIndex(chunks)
    hits = idx.search("ACK 告警阈值", k=3)
    assert hits and hits[0].doc_id == "a"
    assert all(h.doc_id in {"a", "b"} for h in hits)


def test_rrf_fuses_rankings() -> None:
    fused = rrf([["x", "y", "z"], ["w", "x"]], key=lambda s: s)
    assert fused[0] == "x"  # 双路命中分数最高
    assert fused[1] == "w"  # 单路 rank1 高于单路 rank2
    assert set(fused) == {"x", "y", "z", "w"}


async def test_hybrid_search_end_to_end() -> None:
    kb = KnowledgeBase(SqliteVectorStore(":memory:"))
    await kb.ingest(
        title="部署指南",
        content="在阿里云上部署应用，需配置 ACK 集群、SLB 与 HPA 弹性伸缩，灰度先观察再全量。",
    )
    hits = await kb.search("ACK 集群", k=3, strategy="hybrid")
    assert hits and hits[0].title == "部署指南"
    await kb.close()


async def test_keyword_index_refreshed_on_ingest() -> None:
    kb = KnowledgeBase(SqliteVectorStore(":memory:"))
    await kb.ingest(title="运维", content="所有服务部署到 ACK，容量告警阈值 70%。")
    before = await kb.search("应急流程", k=5, strategy="hybrid")
    assert not any("应急" in h.text for h in before)  # 旧库无此关键词
    await kb.ingest(title="应急", content="应急流程：先扩容再回滚，通知值班群。")
    after = await kb.search("应急流程", k=5, strategy="hybrid")
    assert after and "应急流程" in after[0].text  # 新入库文档已进入关键词索引
    await kb.close()


async def test_search_invalid_strategy_raises() -> None:
    kb = KnowledgeBase(SqliteVectorStore(":memory:"))
    with pytest.raises(ValidationError):
        await kb.search("x", strategy="bogus")
    await kb.close()


# ---------- 重排 ----------


async def test_coverage_reranker_reorders() -> None:
    hits = [
        SearchHit(doc_id="a", title="", chunk_index=0, text="这段文本和查询完全无关", score=0.9),
        SearchHit(
            doc_id="b", title="", chunk_index=0, text="ACK 集群容量告警阈值是 70%", score=0.5
        ),
    ]
    out = await CoverageReranker().rerank("ACK 告警阈值", hits, 2)
    assert out[0].doc_id == "b"  # 覆盖度高者排前


async def test_dashscope_reranker_fail_fast() -> None:
    with pytest.raises(RerankUnavailableError):
        await DashScopeReranker().rerank("q", [], 1)


# ---------- 策略对比评测 ----------


async def test_run_retrieval_eval_builtin() -> None:
    kb = KnowledgeBase(SqliteVectorStore(":memory:"))
    ds = builtin_dataset()
    for title, content in ds.corpus:
        await kb.ingest(title=title, content=content)
    report = await run_retrieval_eval(kb, ds, k=5)
    assert report.dataset == "builtin"
    assert report.skipped == []  # 相关标题全部可解析
    assert [s.strategy for s in report.strategies] == ["vector", "hybrid", "hybrid_rerank"]
    by = {s.strategy: s for s in report.strategies}
    for s in report.strategies:
        assert set(s.aggregate) == {"recall@k", "precision@k", "hit_rate", "mrr", "ndcg@k"}
        for v in s.aggregate.values():
            assert 0 <= v <= 1
    # 内置集很简单：任何策略都应整体命中率 >= 0.8，且 hybrid 不劣化 recall
    assert by["hybrid"].aggregate["hit_rate"] >= 0.8
    assert by["hybrid_rerank"].aggregate["hit_rate"] >= 0.8
    assert by["hybrid"].aggregate["recall@k"] >= by["vector"].aggregate["recall@k"]
    await kb.close()


# ---------- RAGAS 式判定 ----------


async def test_coverage_proxy_judge() -> None:
    judge = CoverageProxyJudge()
    ctx = ["ACK 集群容量告警阈值是 70%"]
    assert await judge.answer("阈值", ctx) == ctx[0]
    assert await judge.faithfulness(ctx, "阈值是 70%") >= 0.9
    assert await judge.answer_relevance("ACK 阈值", "ACK 阈值是 70%") >= 0.5


async def test_run_ragas_proxy() -> None:
    kb = KnowledgeBase(SqliteVectorStore(":memory:"))
    await kb.ingest(title="运维", content="所有服务部署到 ACK，容量告警阈值 70%。")
    result = await run_ragas(kb, builtin_dataset().cases[:2], judge=CoverageProxyJudge(), k=3)
    assert len(result["rows"]) == 2
    assert "faithfulness" in result["aggregate"]
    assert "answer_relevance" in result["aggregate"]
    for row in result["rows"]:
        assert 0 <= row["faithfulness"] <= 1
        assert 0 <= row["answer_relevance"] <= 1
        assert row["context_count"] > 0
    await kb.close()


def test_llm_judge_fails_on_mock() -> None:
    with pytest.raises(RagJudgeUnavailableError):
        LLMJudge(MockModelProvider())


# ---------- 存储 / API ----------


async def test_store_all_chunks_roundtrip() -> None:
    store = SqliteVectorStore(":memory:")
    await store.add(
        "d1", "t1", [ChunkRecord(doc_id="d1", chunk_index=0, text="hello world", vector=[0.1, 0.2])]
    )
    chunks = await store.all_chunks()
    assert len(chunks) == 1
    assert chunks[0].text == "hello world"
    assert chunks[0].vector == [0.1, 0.2]
    await store.close()


def test_eval_api_endpoint() -> None:
    kb = KnowledgeBase(SqliteVectorStore(":memory:"))
    with TestClient(create_app(knowledge_base=kb)) as client:
        ds = builtin_dataset()
        for title, content in ds.corpus:
            resp = client.post("/v1/kb/documents", json={"title": title, "content": content})
            assert resp.status_code == 201
        r = client.post("/v1/kb/eval", json={})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["dataset"] == "builtin"
        assert len(body["strategies"]) == 3
        assert body["skipped"] == []
        assert body["ragas"] and "aggregate" in body["ragas"]
        # llm 判定当前需要真实模型 -> fail-fast 503
        r2 = client.post("/v1/kb/eval", json={"judge": "llm"})
        assert r2.status_code == 503
        # 未知策略 -> 422
        r3 = client.post("/v1/kb/eval", json={"strategies": ["bogus"]})
        assert r3.status_code == 422
