"""RAG 知识库 API 模型（M3a）。"""

from __future__ import annotations

from pydantic import BaseModel, Field

# R3：与任务侧对齐做长度上限——封顶防 DoS（10MB 文档会撑出上万 chunk + 全表扫）
MAX_DOCUMENT_CHARS = 100_000


class DocumentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200, description="文档标题")
    content: str = Field(min_length=1, max_length=MAX_DOCUMENT_CHARS, description="文档正文")


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
