"""记忆 API（M3b-FR-4）：长期事实 CRUD + 向量记忆召回 + 上下文块。

路径：/v1/memory/*（facts=项目长期记忆；search=向量记忆；context=F4.3 上下文工程演示）。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from memory.memory import MemoryManager
from memory.schemas import (
    ContextResponse,
    Fact,
    FactPut,
    MemoryHit,
    MemorySearchRequest,
    MemorySearchResponse,
    NoteCreate,
)


def build_memory_router(memory: MemoryManager) -> APIRouter:
    router = APIRouter(prefix="/v1/memory", tags=["memory"])

    @router.put("/facts/{key}", response_model=Fact)
    async def put_fact(key: str, body: FactPut) -> Fact:
        fact = await memory.remember_fact(key, body.value)
        return Fact(
            project_id=fact.project_id,
            key=fact.key,
            value=fact.value,
            updated_at=fact.updated_at,
        )

    @router.get("/facts", response_model=list[Fact])
    async def list_facts() -> list[Fact]:
        facts = await memory.list_facts()
        return [
            Fact(project_id=f.project_id, key=f.key, value=f.value, updated_at=f.updated_at)
            for f in facts
        ]

    @router.get("/facts/{key}", response_model=Fact)
    async def get_fact(key: str) -> Fact:
        fact = await memory.get_fact(key)
        if fact is None:
            raise HTTPException(status_code=404, detail="fact not found")
        return Fact(
            project_id=fact.project_id,
            key=fact.key,
            value=fact.value,
            updated_at=fact.updated_at,
        )

    @router.delete("/facts/{key}", status_code=204)
    async def delete_fact(key: str) -> None:
        if not await memory.forget_fact(key):
            raise HTTPException(status_code=404, detail="fact not found")

    @router.post("/notes", response_model=dict)
    async def remember_note(body: NoteCreate) -> dict:
        note_id = await memory.remember_note(body.text, note_id=body.note_id)
        return {"note_id": note_id}

    @router.post("/search", response_model=MemorySearchResponse)
    async def search_memory(body: MemorySearchRequest) -> MemorySearchResponse:
        hits = await memory.search_memory(body.q, k=body.k)
        return MemorySearchResponse(
            hits=[MemoryHit(source=h.source, text=h.text, score=h.score) for h in hits]
        )

    @router.get("/context", response_model=ContextResponse)
    async def context(q: str = "", budget: int = 1200) -> ContextResponse:
        """F4.3：拼装上下文块（事实 + 按 q 召回的向量记忆）。

        recent（短期对话层）是按 thread 的近期消息，由 TaskManager 在任务开始时
        从 checkpointer 取出并传入——本接口面向工具/调试，不含 recent。
        """
        block = await memory.build_context(query=q or None, budget_chars=budget)
        return ContextResponse(block=block)

    return router
