"""RAG 知识库 API 模型（M3a）。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class DocumentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200, description="文档标题")
    content: str = Field(min_length=1, description="文档正文")


class DocumentSummary(BaseModel):
    doc_id: str
    title: str
    created_at: float


class IngestResponse(BaseModel):
    doc_id: str
    title: str
    chunk_count: int
    chars: int


class SearchHitResponse(BaseModel):
    doc_id: str
    title: str
    chunk_index: int
    text: str
    score: float
