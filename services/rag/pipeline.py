"""RAG 知识库门面（M3a-F5.1/5.3）：入库 -> 切块 -> 向量化 -> 存储；查询 -> 检索（带溯源）。

KnowledgeBase 是上层唯一入口：路由 / 工具 / Web 都只依赖它，不直接碰 store/embedder。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from flare_common.errors import ValidationError
from rag.chunking import split_text
from rag.embedder import Embedder, HashEmbedder
from rag.hybrid import KeywordIndex, rrf
from rag.rerank import CoverageReranker, Reranker
from rag.store import ChunkRecord, DocumentMeta, SearchHit, SqliteVectorStore, VectorStore

SEARCH_STRATEGIES = ("vector", "hybrid", "hybrid_rerank")


@dataclass
class IngestResult:
    doc_id: str
    title: str
    chunk_count: int
    chars: int


class KnowledgeBase:
    def __init__(
        self,
        store: VectorStore | None = None,
        embedder: Embedder | None = None,
        *,
        chunk_size: int = 600,
        overlap: int = 80,
        reranker: Reranker | None = None,
    ) -> None:
        self._store = store or SqliteVectorStore()
        self._embedder = embedder or HashEmbedder()
        self._reranker = reranker or CoverageReranker()  # M3c：开发默认覆盖度重排
        self._chunk_size = chunk_size
        self._overlap = overlap
        self._kw_index: KeywordIndex | None = None  # M3c：BM25 关键词索引（懒构建，变更时失效）

    async def ingest(self, *, title: str, content: str, doc_id: str | None = None) -> IngestResult:
        """入库一份文档：切块 -> 向量化 -> 写入 store。重复 doc_id 会覆盖（upsert）。"""
        if not content.strip():
            raise ValueError("content 不能为空")
        chunks = split_text(content, chunk_size=self._chunk_size, overlap=self._overlap)
        did = doc_id or uuid.uuid4().hex
        vectors = await self._embedder.embed(chunks)
        await self._store.add(
            did,
            title,
            [
                ChunkRecord(doc_id=did, chunk_index=i, text=t, vector=v)
                for i, (t, v) in enumerate(zip(chunks, vectors, strict=True))
            ],
        )
        self._invalidate_keyword_index()
        return IngestResult(doc_id=did, title=title, chunk_count=len(chunks), chars=len(content))

    async def search(self, query: str, *, k: int = 5, strategy: str = "vector") -> list[SearchHit]:
        """检索（M3c）：按策略返回 top-k，命中带 source（title + chunk 序号 + 分数）。

        - vector：纯向量语义（默认，M3a 行为不变）
        - hybrid：向量 + BM25 关键词，RRF 融合
        - hybrid_rerank：hybrid 后再做覆盖度重排
        """
        if not query.strip():
            return []
        if strategy not in SEARCH_STRATEGIES:
            raise ValidationError(f"未知检索策略: {strategy}（可选: {SEARCH_STRATEGIES}）")
        qv = (await self._embedder.embed([query]))[0]
        if strategy == "vector":
            return await self._store.search(qv, k)
        vector_hits = await self._store.search(qv, k * 2)
        kw_hits = (await self._get_keyword_index()).search(query, k * 2)
        fused = rrf([vector_hits, kw_hits], key=lambda h: (h.doc_id, h.chunk_index))
        if strategy == "hybrid_rerank":
            return await self._reranker.rerank(query, fused, k)
        return fused[:k]

    async def _get_keyword_index(self) -> KeywordIndex:
        if self._kw_index is None:
            self._kw_index = KeywordIndex.build_from_chunks(await self._store.all_chunks())
        return self._kw_index

    def _invalidate_keyword_index(self) -> None:
        self._kw_index = None

    async def list_documents(self) -> list[DocumentMeta]:
        return await self._store.list_documents()

    async def delete(self, doc_id: str) -> bool:
        """删除文档（返回是否真的删掉了）。"""
        ok = await self._store.delete(doc_id)
        if ok:
            self._invalidate_keyword_index()
        return ok

    async def close(self) -> None:
        await self._store.close()
