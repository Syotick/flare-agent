"""记忆 API 模型（M3b）。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class FactPut(BaseModel):
    value: str = Field(min_length=1, max_length=4000, description="事实内容")


class Fact(BaseModel):
    project_id: str
    key: str
    value: str
    updated_at: float


class NoteCreate(BaseModel):
    text: str = Field(min_length=1, max_length=4000, description="要记住的笔记/事实")
    note_id: str | None = Field(default=None, description="可选 id（默认自动生成）")


class MemorySearchRequest(BaseModel):
    q: str = Field(min_length=1, description="检索查询")
    k: int = Field(default=4, ge=1, le=20)


class MemoryHit(BaseModel):
    source: str
    text: str
    score: float


class MemorySearchResponse(BaseModel):
    hits: list[MemoryHit]


class ContextResponse(BaseModel):
    block: str
