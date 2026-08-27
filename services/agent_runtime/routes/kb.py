"""知识库 API（M3a-F5.1/5.3）：入库、列表、检索、删除。

路径：/v1/kb/*（与任务 API /v1/tasks/* 并列；Web 后续做知识库管理页时直接消费）。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from rag.pipeline import KnowledgeBase
from rag.schemas import (
    DocumentCreate,
    DocumentSummary,
    IngestResponse,
    SearchHitResponse,
)


def build_kb_router(kb: KnowledgeBase) -> APIRouter:
    router = APIRouter(prefix="/v1/kb", tags=["knowledge-base"])

    @router.post("/documents", response_model=IngestResponse, status_code=201)
    async def ingest_document(body: DocumentCreate) -> IngestResponse:
        """入库一份文档（自动切块 + 向量化）。"""
        result = await kb.ingest(title=body.title, content=body.content)
        return IngestResponse(
            doc_id=result.doc_id,
            title=result.title,
            chunk_count=result.chunk_count,
            chars=result.chars,
        )

    @router.get("/documents", response_model=list[DocumentSummary])
    async def list_documents() -> list[DocumentSummary]:
        metas = await kb.list_documents()
        return [
            DocumentSummary(doc_id=m.doc_id, title=m.title, created_at=m.created_at) for m in metas
        ]

    @router.delete("/documents/{doc_id}", status_code=204)
    async def delete_document(doc_id: str) -> None:
        if not await kb.delete(doc_id):
            raise HTTPException(status_code=404, detail="document not found")

    @router.get("/search", response_model=list[SearchHitResponse])
    async def search_kb(q: str, k: int = Query(5, ge=1, le=20)) -> list[SearchHitResponse]:
        """语义检索：返回 top-k 片段，带来源(title + chunk 序号 + 分数)。k 限 1..20（R4）。"""
        hits = await kb.search(q, k=k)
        return [
            SearchHitResponse(
                doc_id=h.doc_id,
                title=h.title,
                chunk_index=h.chunk_index,
                text=h.text,
                score=h.score,
            )
            for h in hits
        ]

    return router
