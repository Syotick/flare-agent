"""SQLite -> PostgreSQL 迁移 + 双写对账（M5）。

reconcile(src, dst)：比较两个 VectorStore 的文档与 chunk 集合，返回差异明细；
copy_missing(src, dst)：把 src 中 dst 缺失的文档/chunk 补写过去（双写对账闭环）。

本地无 PG 时可用两个 SQLite 库实测：
  PYTHONPATH=services python scripts/reconcile.py --src data/kb.sqlite3 --dst data/kb_copy.sqlite3
有 PG 后：
  PYTHONPATH=services python scripts/reconcile.py --src data/kb.sqlite3 --dst postgresql://flare:flare@localhost:5432/flare
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from rag.pgstore import PgVectorStore
from rag.store import SqliteVectorStore


async def reconcile(src, dst) -> dict:
    """双写对账：返回 src 与 dst 的文档/chunk 差异。"""
    src_docs = {m.doc_id: m for m in await src.list_documents()}
    dst_docs = {m.doc_id: m for m in await dst.list_documents()}
    src_chunks = {(c.doc_id, c.chunk_index) for c in await src.all_chunks()}
    dst_chunks = {(c.doc_id, c.chunk_index) for c in await dst.all_chunks()}
    missing_docs = sorted(set(src_docs) - set(dst_docs))
    missing_chunks = sorted(src_chunks - dst_chunks)
    extra_docs = sorted(set(dst_docs) - set(src_docs))
    return {
        "src_docs": len(src_docs),
        "dst_docs": len(dst_docs),
        "src_chunks": len(src_chunks),
        "dst_chunks": len(dst_chunks),
        "missing_docs": missing_docs,
        "missing_chunks": missing_chunks,
        "extra_docs": extra_docs,
        "consistent": not missing_docs and not missing_chunks,
    }


async def copy_missing(src, dst) -> int:
    """把 src 中 dst 缺失的文档与 chunk 补写到 dst（重新 add，upsert 语义）。"""
    report = await reconcile(src, dst)
    src_all = await src.list_documents()
    src_chunks = await src.all_chunks()
    affected = sorted(set(report["missing_docs"]) | {d for d, _ in report["missing_chunks"]})
    for doc_id in affected:
        meta = next(m for m in src_all if m.doc_id == doc_id)
        chunks = [c for c in src_chunks if c.doc_id == doc_id]
        await dst.add(doc_id, meta.title, chunks)
    return len(affected)


def _build_store(locator: str):
    if locator.startswith("postgres"):
        return PgVectorStore(locator)
    return SqliteVectorStore(locator)


async def _main(src: str, dst: str, fix: bool) -> int:
    src_store = _build_store(src)
    dst_store = _build_store(dst)
    try:
        report = await reconcile(src_store, dst_store)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if not report["consistent"]:
            if fix:
                copied = await copy_missing(src_store, dst_store)
                print("已补齐文档数：", copied)
                report = await reconcile(src_store, dst_store)
                print("修复后 consistent:", report["consistent"])
                return 0 if report["consistent"] else 1
            print("存在差异：", len(report["missing_docs"]), "个文档缺失")
            return 1
        print("一致：无需修复")
        return 0
    finally:
        await src_store.close()
        await dst_store.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="SQLite->PG 迁移双写对账")
    parser.add_argument("--src", required=True, help="源存储：sqlite 路径或 postgres dsn")
    parser.add_argument("--dst", required=True, help="目标存储：sqlite 路径或 postgres dsn")
    parser.add_argument("--fix", action="store_true", help="补齐缺失数据（双写修复）")
    args = parser.parse_args()
    sys.exit(asyncio.run(_main(args.src, args.dst, args.fix)))


if __name__ == "__main__":
    main()
