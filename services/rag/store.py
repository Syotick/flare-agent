"""向量存储（M3a-F5.1）。

统一 async 接口（VectorStore 协议）：
  - SqliteVectorStore：本地开发（aiosqlite 落盘，余弦相似度 Python 计算；数据可跨重启复用）
  - PgVectorStore：生产占位（pgvector，M5 云原生阶段落地，未就绪时 fail-fast）

注：本实现假定向量已 L2 归一化，检索直接做点积 = 余弦相似度。
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Protocol

import aiosqlite

from flare_common.errors import FlareError


class VectorStoreUnavailableError(FlareError):
    code = "VECTOR_STORE_NOT_READY"
    status_code = 503


@dataclass
class ChunkRecord:
    doc_id: str
    chunk_index: int
    text: str
    vector: list[float]


@dataclass
class SearchHit:
    doc_id: str
    title: str
    chunk_index: int
    text: str
    score: float


@dataclass
class DocumentMeta:
    doc_id: str
    title: str
    created_at: float


class VectorStore(Protocol):
    async def add(self, doc_id: str, title: str, chunks: list[ChunkRecord]) -> None: ...
    async def search(self, vector: list[float], k: int) -> list[SearchHit]: ...
    async def list_documents(self) -> list[DocumentMeta]: ...
    async def delete(self, doc_id: str) -> bool: ...
    async def close(self) -> None: ...


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


class SqliteVectorStore:
    """本地向量库：SQLite 双表（documents / chunks）+ 余弦相似度全扫。

    开发规模（几百文档）足够；生产 M5 迁 pgvector / Milvus 走同协议。
    """

    def __init__(self, path: str | None = None) -> None:
        self._path = path or ":memory:"
        self._conn: aiosqlite.Connection | None = None
        self._lock = asyncio.Lock()

    async def _db(self) -> aiosqlite.Connection:
        if self._conn is None:
            self._conn = await aiosqlite.connect(self._path)
            self._conn.row_factory = aiosqlite.Row
            await self._conn.execute("""CREATE TABLE IF NOT EXISTS documents(
                       doc_id TEXT PRIMARY KEY,
                       title TEXT NOT NULL,
                       created_at REAL NOT NULL)""")
            await self._conn.execute("""CREATE TABLE IF NOT EXISTS chunks(
                       doc_id TEXT NOT NULL,
                       chunk_index INTEGER NOT NULL,
                       text TEXT NOT NULL,
                       vector TEXT NOT NULL,
                       PRIMARY KEY(doc_id, chunk_index))""")
            await self._conn.commit()
        return self._conn

    async def add(self, doc_id: str, title: str, chunks: list[ChunkRecord]) -> None:
        db = await self._db()
        async with self._lock:
            await db.execute(
                "INSERT OR REPLACE INTO documents(doc_id, title, created_at) VALUES(?,?,?)",
                (doc_id, title, time.time()),
            )
            await db.executemany(
                "INSERT OR REPLACE INTO chunks(doc_id, chunk_index, text, vector) VALUES(?,?,?,?)",
                [(c.doc_id, c.chunk_index, c.text, json.dumps(c.vector)) for c in chunks],
            )
            await db.commit()

    async def search(self, vector: list[float], k: int) -> list[SearchHit]:
        db = await self._db()
        async with self._lock:
            cur = await db.execute("SELECT doc_id, chunk_index, text, vector FROM chunks")
            rows = await cur.fetchall()
            cur2 = await db.execute("SELECT doc_id, title FROM documents")
            metas = {r["doc_id"]: r["title"] for r in await cur2.fetchall()}
        scored: list[SearchHit] = []
        for row in rows:
            v = json.loads(row["vector"])
            scored.append(
                SearchHit(
                    doc_id=row["doc_id"],
                    title=metas.get(row["doc_id"], row["doc_id"]),
                    chunk_index=row["chunk_index"],
                    text=row["text"],
                    score=_dot(vector, v),
                )
            )
        scored.sort(key=lambda h: h.score, reverse=True)
        return scored[:k]

    async def list_documents(self) -> list[DocumentMeta]:
        db = await self._db()
        async with self._lock:
            cur = await db.execute(
                "SELECT doc_id, title, created_at FROM documents ORDER BY created_at DESC"
            )
            rows = await cur.fetchall()
        return [
            DocumentMeta(doc_id=r["doc_id"], title=r["title"], created_at=r["created_at"])
            for r in rows
        ]

    async def delete(self, doc_id: str) -> bool:
        db = await self._db()
        async with self._lock:
            cur = await db.execute("DELETE FROM documents WHERE doc_id=?", (doc_id,))
            await db.execute("DELETE FROM chunks WHERE doc_id=?", (doc_id,))
            await db.commit()
        return cur.rowcount > 0

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None


class PgVectorStore:
    """生产向量库占位：pgvector（M5 云原生阶段接入）。

    未就绪时所有操作 fail-fast 抛 VectorStoreUnavailableError（R4 原则：宁可报错，不要静默降级）。
    """

    _message = "PgVectorStore 尚未接入（M5 云原生阶段引入 pgvector）"

    async def _not_ready(self, *args, **kwargs):
        raise VectorStoreUnavailableError(self._message)

    add = _not_ready
    search = _not_ready
    list_documents = _not_ready
    delete = _not_ready
    close = _not_ready
