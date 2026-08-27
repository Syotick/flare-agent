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


# ---------- M3c 评测 ----------


class EvalCaseIn(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    relevant_titles: list[str] = Field(default_factory=list, max_length=20)


class EvalRequest(BaseModel):
    k: int = Field(default=5, ge=1, le=20)
    cases: list[EvalCaseIn] | None = None  # 缺省用内置评测集（要求相关文档已入库）
    strategies: list[str] | None = None  # 缺省 vector/hybrid/hybrid_rerank 全跑
    judge: str = Field(default="proxy", pattern="^(proxy|llm)$")  # RAGAS 判定方式


class EvalStrategyOut(BaseModel):
    strategy: str
    k: int
    aggregate: dict
    per_query: list[dict]


class EvalResponse(BaseModel):
    dataset: str
    k: int
    strategies: list[EvalStrategyOut]
    skipped: list[dict]
    ragas: dict | None = None  # proxy/llm 判定结果（llm 需真实模型）
