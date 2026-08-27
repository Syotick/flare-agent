"""评测运行器（M3c）：对多个检索策略跑同一数据集，输出可对比的报告。

流程：语料已入库的 KnowledgeBase + EvalCase 列表 -> 各策略检索 -> 算指标 -> 汇总。
相关文档按标题解析（title -> doc_id），解析不到就进 skipped（诚实报告，不假装覆盖）。
"""

from __future__ import annotations

from dataclasses import dataclass

from rag.eval.dataset import EvalCase, EvalDataset
from rag.eval.metrics import (
    aggregate,
    hit_at_k,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)
from rag.pipeline import SEARCH_STRATEGIES, KnowledgeBase


@dataclass
class StrategyReport:
    strategy: str
    k: int
    aggregate: dict
    per_query: list[dict]


@dataclass
class EvalReport:
    dataset: str
    k: int
    strategies: list[StrategyReport]
    skipped: list[dict]


async def resolve_relevant(
    kb: KnowledgeBase, cases: list[EvalCase]
) -> tuple[list[tuple[str, set[str]]], list[dict]]:
    """把相关标题解析成 doc_id；解析不到的相关项进 skipped。"""
    metas = await kb.list_documents()
    title2id = {m.title: m.doc_id for m in metas}
    resolved: list[tuple[str, set[str]]] = []
    skipped: list[dict] = []
    for case in cases:
        rel = [title2id[t] for t in case.relevant_titles if t in title2id]
        if not rel:
            skipped.append({"query": case.query, "relevant_titles": case.relevant_titles})
            continue
        resolved.append((case.query, set(rel)))
    return resolved, skipped


async def run_retrieval_eval(
    kb: KnowledgeBase,
    dataset: EvalDataset | list[EvalCase],
    *,
    k: int = 5,
    strategies: tuple[str, ...] | list[str] = SEARCH_STRATEGIES,
) -> EvalReport:
    """对给定数据集跑多个检索策略，返回对比报告（不负责入库语料）。"""
    cases = dataset.cases if isinstance(dataset, EvalDataset) else list(dataset)
    resolved, skipped = await resolve_relevant(kb, cases)
    reports: list[StrategyReport] = []
    for strategy in strategies:
        per_query: list[dict] = []
        for query, rel in resolved:
            hits = await kb.search(query, k=k, strategy=strategy)
            hit_docs = [h.doc_id for h in hits]
            per_query.append(
                {
                    "query": query,
                    "relevant": len(rel),
                    "recall@k": recall_at_k(hit_docs, rel, k),
                    "precision@k": precision_at_k(hit_docs, rel, k),
                    "hit_rate": hit_at_k(hit_docs, rel, k),
                    "mrr": reciprocal_rank(hit_docs, rel),
                    "ndcg@k": ndcg_at_k(hit_docs, rel, k),
                }
            )
        reports.append(
            StrategyReport(
                strategy=strategy, k=k, per_query=per_query, aggregate=aggregate(per_query)
            )
        )
    return EvalReport(
        dataset=getattr(dataset, "name", "custom"), k=k, strategies=reports, skipped=skipped
    )
