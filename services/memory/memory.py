"""MemoryManager：分层记忆门面（M3b-FR-4）。

职责：
  - 项目长期事实：key->value，按 project_id 隔离（开发 SQLite，生产 PG 同表结构）
  - 向量记忆：把笔记/事实向量化存入 VectorStore，语义召回（复用 rag 协议）
  - 上下文工程：build_context() 把三层记忆按预算拼成可注入 Agent 的块

不重复造轮子：向量存储/嵌入直接注入 rag.store / rag.embedder 实现。
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass

import aiosqlite

from memory.context import assemble
from rag.embedder import Embedder, HashEmbedder
from rag.store import SqliteVectorStore, VectorStore


@dataclass
class MemoryHit:
    source: str
    text: str
    score: float


@dataclass
class MemoryFact:
    project_id: str
    key: str
    value: str
    updated_at: float


class MemoryManager:
    """分层记忆门面；facts 存 SQLite 表，笔记走向量存储。"""

    def __init__(
        self,
        facts_path: str | None = None,
        *,
        vector_store: VectorStore | None = None,
        embedder: Embedder | None = None,
        project_id: str = "default",
        context_budget_chars: int = 1200,
    ) -> None:
        self._facts_path = facts_path or ":memory:"
        self._conn: aiosqlite.Connection | None = None
        self._lock = asyncio.Lock()
        self._vector = vector_store or SqliteVectorStore()
        self._embedder = embedder or HashEmbedder()
        self._project_id = project_id
        self._budget = context_budget_chars

    # ---------- 事实库（项目长期记忆） ----------

    async def _db(self) -> aiosqlite.Connection:
        if self._conn is None:
            self._conn = await aiosqlite.connect(self._facts_path)
            self._conn.row_factory = aiosqlite.Row
            await self._conn.execute("""CREATE TABLE IF NOT EXISTS facts(
                       project_id TEXT NOT NULL,
                       key TEXT NOT NULL,
                       value TEXT NOT NULL,
                       updated_at REAL NOT NULL,
                       PRIMARY KEY(project_id, key))""")
            await self._conn.commit()
        return self._conn

    async def remember_fact(
        self, key: str, value: str, *, project_id: str | None = None
    ) -> MemoryFact:
        """写一条长期事实（upsert）。"""
        pid = project_id or self._project_id
        db = await self._db()
        async with self._lock:
            await db.execute(
                "INSERT OR REPLACE INTO facts(project_id, key, value, updated_at) VALUES(?,?,?,?)",
                (pid, key, value, time.time()),
            )
            await db.commit()
        return await self.get_fact(key, project_id=pid)

    async def get_fact(self, key: str, *, project_id: str | None = None) -> MemoryFact | None:
        db = await self._db()
        async with self._lock:
            cur = await db.execute(
                "SELECT project_id, key, value, updated_at FROM facts WHERE project_id=? AND key=?",
                (project_id or self._project_id, key),
            )
            row = await cur.fetchone()
        if row is None:
            return None
        return MemoryFact(
            project_id=row["project_id"],
            key=row["key"],
            value=row["value"],
            updated_at=row["updated_at"],
        )

    async def list_facts(self, *, project_id: str | None = None) -> list[MemoryFact]:
        db = await self._db()
        async with self._lock:
            cur = await db.execute(
                "SELECT project_id, key, value, updated_at FROM facts "
                "WHERE project_id=? ORDER BY updated_at DESC",
                (project_id or self._project_id,),
            )
            rows = await cur.fetchall()
        return [
            MemoryFact(
                project_id=r["project_id"],
                key=r["key"],
                value=r["value"],
                updated_at=r["updated_at"],
            )
            for r in rows
        ]

    async def forget_fact(self, key: str, *, project_id: str | None = None) -> bool:
        db = await self._db()
        async with self._lock:
            cur = await db.execute(
                "DELETE FROM facts WHERE project_id=? AND key=?",
                (project_id or self._project_id, key),
            )
            await db.commit()
        return cur.rowcount > 0

    # ---------- 向量记忆（用户/组织级语义召回） ----------

    async def remember_note(self, text: str, *, note_id: str | None = None) -> str:
        """记住一条笔记/事实到向量记忆（语义召回用）。返回 note_id。"""
        nid = note_id or uuid.uuid4().hex
        (vec,) = await self._embedder.embed([text])
        from rag.store import ChunkRecord

        await self._vector.add(
            nid,
            f"memory:{nid}",
            [ChunkRecord(doc_id=nid, chunk_index=0, text=text, vector=vec)],
        )
        return nid

    async def search_memory(self, query: str, *, k: int = 4) -> list[MemoryHit]:
        """语义召回向量记忆（不带事实库）。"""
        if not query.strip():
            return []
        qv = (await self._embedder.embed([query]))[0]
        hits = await self._vector.search(qv, k)
        return [MemoryHit(source=h.title, text=h.text, score=h.score) for h in hits]

    # ---------- 上下文工程（F4.3） ----------

    async def build_context(
        self,
        *,
        recent: list[str] | None = None,
        query: str | None = None,
        budget_chars: int | None = None,
    ) -> str:
        """拼装三层记忆上下文块：事实（全部）+ 向量（按 query 召回）+ 近期对话。"""
        facts = await self.list_facts()
        hits: list[MemoryHit] = []
        if query:
            hits = await self.search_memory(query, k=3)
        return assemble(
            recent=recent,
            facts=[(f.key, f.value) for f in facts],
            hits=[(h.source, h.text, h.score) for h in hits],
            budget_chars=budget_chars or self._budget,
        )

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None
        await self._vector.close()
