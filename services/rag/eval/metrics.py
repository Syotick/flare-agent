"""确定性检索评测指标（M3c）：不依赖 LLM，可离线量化检索质量。

相关 = 该查询在知识库中应当命中的文档（doc_id 集合）。
    recall@k：相关文档被召回的比例（关心"别漏"）；
    precision@k：top-k 里相关的比例（关心"别脏"）；
    hit_rate：top-k 是否命中至少一条相关；
    MRR：第一个相关文档排位的倒数（关心"第一名"对不对）；
    NDCG@k：带位置折损的相关度（关心整体排序质量）。
"""

from __future__ import annotations

import math


def recall_at_k(hits: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    return sum(1 for d in hits[:k] if d in relevant) / len(relevant)


def precision_at_k(hits: list[str], relevant: set[str], k: int) -> float:
    if k <= 0:
        return 0.0
    return sum(1 for d in hits[:k] if d in relevant) / k


def hit_at_k(hits: list[str], relevant: set[str], k: int) -> float:
    return 1.0 if any(d in relevant for d in hits[:k]) else 0.0


def reciprocal_rank(hits: list[str], relevant: set[str]) -> float:
    for i, d in enumerate(hits, start=1):
        if d in relevant:
            return 1.0 / i
    return 0.0


def ndcg_at_k(hits: list[str], relevant: set[str], k: int) -> float:
    """二值相关 NDCG：DCG = sum(rel / log2(i+1))，IDCG = 全相关理想排序。"""
    top = hits[:k]
    dcg = sum(1.0 / math.log2(i + 1) for i, d in enumerate(top, start=1) if d in relevant)
    n = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, n + 1))
    return dcg / idcg if idcg else 0.0


def aggregate(per_query: list[dict]) -> dict:
    """把每条的指标聚合成整体均值（保留 4 位小数）。"""
    keys = ("recall@k", "precision@k", "hit_rate", "mrr", "ndcg@k")
    n = len(per_query)
    if n == 0:
        return {k: 0.0 for k in keys}
    return {k: round(sum(q[k] for q in per_query) / n, 4) for k in keys}
