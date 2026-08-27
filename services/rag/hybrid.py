"""混合检索（M3c）：BM25 关键词 + 向量语义，RRF 融合。

真理：向量召回擅长"语义相近"但可能漏精确关键词（尤其专有名词/编号/代码）；
    BM25 擅长字面命中但不懂改写。两者融合（Reciprocal Rank Fusion）通常优于单一策略——
    M3c 用评测数据量化这个差距，而不是拍脑袋。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from rag.lexical import tokenize
from rag.store import ChunkRecord

BM25_K1 = 1.5
BM25_B = 0.75


@dataclass
class KeywordHit:
    doc_id: str
    chunk_index: int
    text: str
    score: float


class KeywordIndex:
    """BM25 关键词索引：token -> 倒排(tf)，查询时按 BM25 打分取 top-k。"""

    def __init__(self, chunks: list[ChunkRecord]) -> None:
        self._chunks = list(chunks)
        self._n = len(chunks)
        self._postings: dict[str, dict[int, int]] = {}  # token -> {chunk_idx: tf}
        self._doc_len: list[int] = []
        for idx, c in enumerate(chunks):
            toks = tokenize(c.text)
            self._doc_len.append(len(toks))
            counts: dict[str, int] = {}
            for t in toks:
                counts[t] = counts.get(t, 0) + 1
            for t, tf in counts.items():
                self._postings.setdefault(t, {})[idx] = tf
        self._avgdl = (sum(self._doc_len) / self._n) if self._n else 0.0

    @classmethod
    def build_from_chunks(cls, chunks: list[ChunkRecord]) -> KeywordIndex:
        return cls(chunks)

    def search(self, query: str, k: int = 10) -> list[KeywordHit]:
        """BM25 检索，返回按分数降序的 top-k 片段。"""
        if not self._n or not query.strip():
            return []
        q_tokens = set(tokenize(query))
        scores: dict[int, float] = {}
        for t in q_tokens:
            postings = self._postings.get(t)
            if not postings:
                continue
            df = len(postings)
            idf = math.log(1 + (self._n - df + 0.5) / (df + 0.5))
            for idx, tf in postings.items():
                dl = self._doc_len[idx]
                denom = tf + BM25_K1 * (
                    1 - BM25_B + BM25_B * (dl / self._avgdl if self._avgdl else 0)
                )
                scores[idx] = scores.get(idx, 0.0) + idf * (tf * (BM25_K1 + 1)) / denom
        ranked = sorted(scores.items(), key=lambda kv: -kv[1])
        return [
            KeywordHit(
                doc_id=self._chunks[idx].doc_id,
                chunk_index=self._chunks[idx].chunk_index,
                text=self._chunks[idx].text,
                score=s,
            )
            for idx, s in ranked[:k]
        ]


def rrf(rankings: list[list[Any]], *, key, k: int = 60) -> list[Any]:
    """Reciprocal Rank Fusion：对多路排序各按 1/(k+rank) 累分，再按总分排序。

    不要求各路分数可比（向量余弦 vs BM25），只吃排名——这正是 RRF 的价值。
    """
    fused: dict[Any, float] = {}
    items: dict[Any, Any] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            ident = key(item)
            if ident not in items:  # 只保留首次出现的对象（SearchHit 优先，保字段完整）
                items[ident] = item
            fused[ident] = fused.get(ident, 0.0) + 1.0 / (k + rank)
    return [items[i] for i, _ in sorted(fused.items(), key=lambda kv: -kv[1])]
