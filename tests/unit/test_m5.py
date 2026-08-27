"""M5 测试：多租户 / 任务存储(内存+SQLite+Redis) / PgVectorStore fail-fast / 双写对账 / OTel。"""

from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import MemorySaver
from scripts.reconcile import copy_missing, reconcile

from agent_runtime.task_store import (
    InMemoryTaskStore,
    RedisTaskStore,
    SqliteTaskStore,
    TaskStore,
    TaskStoreUnavailableError,
)
from agent_runtime.tasks import TaskManager
from flare_common.tenant import TenantMiddleware, get_tenant_id
from model_gateway.mock import MockModelProvider
from rag.pgstore import PgVectorStore, VectorStoreUnavailableError, _search_sql, _vector_literal
from rag.store import ChunkRecord, SqliteVectorStore
from tools_gateway.builtin import create_default_registry


async def _mem_saver_factory():
    return MemorySaver()


def _make_task_manager(store: TaskStore) -> TaskManager:
    return TaskManager(
        registry=create_default_registry(),
        llm=MockModelProvider(),
        checkpointer_factory=_mem_saver_factory,
        store=store,
    )


# ---------- 多租户 ----------


def test_tenant_middleware_sets_contextvar_and_echoes_header() -> None:
    app = FastAPI()

    @app.get("/who")
    async def who() -> dict:
        return {"tenant": get_tenant_id()}

    app.add_middleware(TenantMiddleware)
    with TestClient(app) as client:
        r = client.get("/who", headers={"X-Tenant-Id": "alice"})
        assert r.status_code == 200
        assert r.json()["tenant"] == "alice"
        assert r.headers.get("X-Tenant-Id") == "alice"
        r2 = client.get("/who")
        assert r2.json()["tenant"] == "default"
        assert r2.headers.get("X-Tenant-Id") == "default"


# ---------- 任务存储 ----------


async def test_in_memory_store_roundtrip() -> None:
    store = InMemoryTaskStore()
    tm = _make_task_manager(store)
    task = await tm.create("hello", tenant_id="t1")
    got = await store.get(task.task_id)
    assert got is not None and got.tenant_id == "t1"
    assert len(await store.list()) == 1
    assert await store.delete(task.task_id) is True


async def test_sqlite_store_persists_across_instances(tmp_path) -> None:
    path = str(tmp_path / "tasks.sqlite3")
    store1 = SqliteTaskStore(path)
    tm = _make_task_manager(store1)
    task = await tm.create("持久化任务", max_steps=1, tenant_id="bob")
    for _ in range(100):
        if task.status in ("completed", "failed", "budget_exceeded"):
            break
        await asyncio.sleep(0.01)
    await asyncio.sleep(0.1)  # 等终态后的 finally 落盘完成，再关连接
    await store1.close()

    # 新实例（模拟重启）仍能读到该任务
    store2 = SqliteTaskStore(path)
    got = await store2.get(task.task_id)
    assert got is not None
    assert got.status == "completed"
    assert got.tenant_id == "bob"
    assert got.result is not None
    await store2.close()


async def test_redis_store_unreachable_fails_fast() -> None:
    store = RedisTaskStore("redis://127.0.0.1:1/0")  # 端口 1 必拒连
    with pytest.raises(TaskStoreUnavailableError):
        await store.get("x")


async def test_task_record_carries_tenant_id() -> None:
    tm = _make_task_manager(InMemoryTaskStore())
    task = await tm.create("hi", tenant_id="alice")
    assert task.tenant_id == "alice"
    task2 = await tm.create("hi2")
    assert task2.tenant_id == "default"


# ---------- PgVectorStore ----------


def test_pg_sql_helpers_are_well_formed() -> None:
    assert "kb_chunks" in _search_sql("kb_chunks")
    assert "<=>" in _search_sql("kb_chunks")
    assert "CREATE EXTENSION IF NOT EXISTS vector" in __import__(
        "rag.pgstore", fromlist=["_schema_sql"]
    )._schema_sql("kb_chunks")
    assert _vector_literal([1.0, 2.5]) == "[1.0,2.5]"


async def test_pg_store_unreachable_fails_fast() -> None:
    store = PgVectorStore("postgresql://no-such-host-flare:5432/flare")
    with pytest.raises(VectorStoreUnavailableError):
        await store.add("d1", "t", [ChunkRecord("d1", 0, "文本", [1.0, 0.0])])


# ---------- 双写对账 ----------


async def test_reconcile_detects_and_fixes_missing(tmp_path) -> None:
    src = SqliteVectorStore(":memory:")
    dst = SqliteVectorStore(":memory:")
    await src.add(
        "doc1",
        "对账文档",
        [
            ChunkRecord("doc1", 0, "第一块", [0.5, 0.5]),
            ChunkRecord("doc1", 1, "第二块", [0.1, 0.9]),
        ],
    )
    await src.add("doc2", "另一篇", [ChunkRecord("doc2", 0, "内容", [0.2, 0.8])])

    report = await reconcile(src, dst)
    assert report["consistent"] is False
    assert report["missing_docs"] == ["doc1", "doc2"]
    assert report["src_docs"] == 2
    assert report["dst_docs"] == 0

    copied = await copy_missing(src, dst)
    assert copied == 2
    report2 = await reconcile(src, dst)
    assert report2["consistent"] is True
    assert report2["src_chunks"] == report2["dst_chunks"] == 3
    await src.close()
    await dst.close()


# ---------- OTel ----------


def test_otel_noop_without_endpoint() -> None:
    import flare_common.otel as otel

    otel._initialized = False
    assert otel.init_tracing("svc", None) is False


def test_otel_initializes_and_records_spans() -> None:
    from opentelemetry.sdk.trace.export import SpanExporter

    import flare_common.otel as otel

    class NoopExporter(SpanExporter):
        def export(self, spans, timeout_millis=0):
            return None

        def shutdown(self):
            return None

    otel._initialized = False
    assert (
        otel.init_tracing(
            "svc",
            "http://127.0.0.1:4318",
            exporter_factory=lambda **kw: NoopExporter(),
        )
        is True
    )
    tracer = otel.get_tracer()
    with tracer.start_as_current_span("m5-test") as span:
        assert span.is_recording()
