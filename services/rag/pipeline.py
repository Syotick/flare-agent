"""RAG 知识库门面（M3a-F5.1/5.3）：入库 -> 切块 -> 向量化 -> 存储；查询 -> 检索（带溯源）。

KnowledgeBase 是上层唯一入口：路由 / 工具 / Web 都只依赖它，不直接碰 store/embedder。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from rag.chunking import split_text
from rag.embedder import Embedder, HashEmbedder
from rag.store import ChunkRecord, DocumentMeta, SearchHit, SqliteVectorStore, VectorStore


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
    ) -> None:
        self._store = store or SqliteVectorStore()
        self._embedder = embedder or HashEmbedder()
        self._chunk_size = chunk_size
        self._overlap = overlap

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
        return IngestResult(doc_id=did, title=title, chunk_count=len(chunks), chars=len(content))

    async def search(self, query: str, *, k: int = 5) -> list[SearchHit]:
        """检索：查询 -> 向量化 -> top-k，命中带 source（title + chunk 序号 + 分数）。"""
        if not query.strip():
            return []
        qv = (await self._embedder.embed([query]))[0]
        return await self._store.search(qv, k)

    async def list_documents(self) -> list[DocumentMeta]:
        return await self._store.list_documents()

    async def delete(self, doc_id: str) -> bool:
        """删除文档（返回是否真的删掉了）。"""
        return await self._store.delete(doc_id)

    async def close(self) -> None:
        await self._store.close()
