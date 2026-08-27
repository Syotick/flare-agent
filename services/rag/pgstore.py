"""PgVectorStore：生产向量存储（M5 云原生）。

PostgreSQL + pgvector 扩展，同协议实现 VectorStore（对齐 rag/store.py）：
  - documents 表（元数据）+ 分表 kb_chunks / memory_chunks（按域隔离）；
  - 检索用余弦距离（vector <=>），score = 1 - distance；
  - 未装 asyncpg / 连不上 PG -> VectorStoreUnavailableError（fail-fast，绝不静默降级）。

纯 SQL 函数（_schema_sql/_search_sql 等）为无副作用可单测代码。
"""

from __future__ import annotations

import time

from flare_common.errors import FlareError


class VectorStoreUnavailableError(FlareError):
    code = "VECTOR_STORE_UNAVAILABLE"
    status_code = 503


def _vector_literal(vector: list[float]) -> str:
    """list[float] -> pgvector 字面量 '[0.1,0.2,...]'。"""
    return "[" + ",".join(str(x) for x in vector) + "]"


def _schema_sql(chunk_table: str) -> str:
    return (
        "CREATE EXTENSION IF NOT EXISTS vector;\n"
        "CREATE TABLE IF NOT EXISTS documents(\n"
        "    doc_id TEXT PRIMARY KEY,\n"
        "    title TEXT NOT NULL,\n"
        "    created_at DOUBLE PRECISION NOT NULL\n"
        ");\n"
        f"CREATE TABLE IF NOT EXISTS {chunk_table}(\n"
        "    doc_id TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,\n"
        "    chunk_index INTEGER NOT NULL,\n"
        "    text TEXT NOT NULL,\n"
        "    vector vector NOT NULL,\n"
        "    PRIMARY KEY (doc_id, chunk_index)\n"
        ");\n"
        f"CREATE INDEX IF NOT EXISTS idx_{chunk_table}_vector ON {chunk_table} "
        "USING hnsw (vector vector_cosine_ops);\n"
    )


def _insert_doc_sql() -> str:
    return (
        "INSERT INTO documents(doc_id, title, created_at) VALUES($1, $2, $3)"
        " ON CONFLICT (doc_id) DO UPDATE SET title = EXCLUDED.title"
    )


def _insert_chunk_sql(chunk_table: str) -> str:
    return (
        f"INSERT INTO {chunk_table}(doc_id, chunk_index, text, vector) "
        "VALUES($1, $2, $3, $4::vector) "
        "ON CONFLICT (doc_id, chunk_index) DO UPDATE SET "
        "text = EXCLUDED.text, vector = EXCLUDED.vector"
    )


def _search_sql(chunk_table: str) -> str:
    return (
        f"SELECT c.doc_id, d.title, c.chunk_index, c.text, "
        "GREATEST(0.0, 1.0 - (c.vector <=> $1::vector)) AS score "
        f"FROM {chunk_table} c JOIN documents d ON d.doc_id = c.doc_id "
        "ORDER BY c.vector <=> $1::vector ASC LIMIT $2"
    )


def _all_chunks_sql(chunk_table: str) -> str:
    return (
        f"SELECT doc_id, chunk_index, text, vector::text AS vector FROM {chunk_table} "
        "ORDER BY doc_id, chunk_index"
    )


class PgVectorStore:
    """PostgreSQL + pgvector 向量存储（同协议实现 VectorStore）。"""

    def __init__(self, dsn: str, *, chunk_table: str = "kb_chunks") -> None:
        self._dsn = dsn
        self._chunk_table = chunk_table
        self._pool = None

    @property
    def chunk_table(self) -> str:
        return self._chunk_table

    async def _acquire_pool(self):
        if self._pool is not None:
            return self._pool
        try:
            import asyncpg
        except ImportError as exc:
            raise VectorStoreUnavailableError("缺少 asyncpg 依赖（pip install asyncpg）") from exc
        try:
            self._pool = await asyncpg.create_pool(self._dsn, min_size=1, max_size=5)
        except Exception as exc:  # noqa: BLE001 - 连接失败统一转可用性错误
            raise VectorStoreUnavailableError(f"无法连接 PostgreSQL: {exc}") from exc
        return self._pool

    async def _ensure_schema(self) -> None:
        pool = await self._acquire_pool()
        async with pool.acquire() as conn:
            await conn.execute(_schema_sql(self._chunk_table))

    async def add(self, doc_id: str, title: str, chunks: list) -> None:
        await self._ensure_schema()
        pool = await self._acquire_pool()
        async with pool.acquire() as conn, conn.transaction():
            await conn.execute(_insert_doc_sql(), doc_id, title, time.time())
            for c in chunks:
                await conn.execute(
                    _insert_chunk_sql(self._chunk_table),
                    c.doc_id,
                    c.chunk_index,
                    c.text,
                    _vector_literal(c.vector),
                )

    async def search(self, vector: list, k: int) -> list:
        await self._ensure_schema()
        pool = await self._acquire_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(_search_sql(self._chunk_table), _vector_literal(vector), k)
        from rag.store import SearchHit

        return [
            SearchHit(
                doc_id=r["doc_id"],
                title=r["title"],
                chunk_index=r["chunk_index"],
                text=r["text"],
                score=float(r["score"]),
            )
            for r in rows
        ]

    async def all_chunks(self) -> list:
        await self._ensure_schema()
        pool = await self._acquire_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(_all_chunks_sql(self._chunk_table))
        from rag.store import ChunkRecord

        return [
            ChunkRecord(
                doc_id=r["doc_id"],
                chunk_index=r["chunk_index"],
                text=r["text"],
                vector=[float(x) for x in r["vector"][1:-1].split(",") if x],
            )
            for r in rows
        ]

    async def list_documents(self) -> list:
        await self._ensure_schema()
        pool = await self._acquire_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT doc_id, title, created_at FROM documents ORDER BY created_at"
            )
        from rag.store import DocumentMeta

        return [
            DocumentMeta(
                doc_id=r["doc_id"],
                title=r["title"],
                created_at=float(r["created_at"]),
            )
            for r in rows
        ]

    async def delete(self, doc_id: str) -> bool:
        await self._ensure_schema()
        pool = await self._acquire_pool()
        async with pool.acquire() as conn:
            r = await conn.execute("DELETE FROM documents WHERE doc_id = $1", doc_id)
        return "DELETE 1" in r

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
