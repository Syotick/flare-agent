"""任务存储（M5）：TaskManager 的持久化抽象，memory -> sqlite -> redis 演进。

- InMemoryTaskStore：默认（进程内，行为与 M2 一致）；
- SqliteTaskStore：单机持久（重启可查历史任务，本地可测）；
- RedisTaskStore：多实例共享（无 redis 依赖/连不上 -> TaskStoreUnavailableError fail-fast）。
"""

from __future__ import annotations

import dataclasses
import json
from abc import ABC, abstractmethod
from pathlib import Path

from flare_common.errors import FlareError


class TaskStoreUnavailableError(FlareError):
    code = "TASK_STORE_UNAVAILABLE"
    status_code = 503


def _record_to_dict(record) -> dict:
    """TaskRecord -> JSON 安全的 dict（dataclass 嵌套递归转 dict）。"""
    return dataclasses.asdict(record)


def _record_from_dict(d: dict):
    """dict -> TaskRecord（延迟导入避免与 tasks.py 循环依赖）。"""
    from agent_runtime.tasks import TaskRecord

    return TaskRecord(**d)


class TaskStore(ABC):
    @abstractmethod
    async def create(self, task) -> None: ...

    @abstractmethod
    async def save(self, task) -> None: ...

    @abstractmethod
    async def get(self, task_id: str): ...

    @abstractmethod
    async def list(self, limit: int = 200) -> list: ...

    @abstractmethod
    async def delete(self, task_id: str) -> bool: ...

    @abstractmethod
    async def close(self) -> None:
        """释放连接等资源。"""


class InMemoryTaskStore(TaskStore):
    """进程内存储（默认，行为与 M2 一致）。"""

    def __init__(self) -> None:
        self._tasks: dict = {}

    async def create(self, task) -> None:
        self._tasks[task.task_id] = task

    async def save(self, task) -> None:
        self._tasks[task.task_id] = task

    async def get(self, task_id: str):
        return self._tasks.get(task_id)

    async def list(self, limit: int = 200) -> list:
        recs = sorted(self._tasks.values(), key=lambda t: t.created_at, reverse=True)
        return recs[:limit]

    async def delete(self, task_id: str) -> bool:
        return self._tasks.pop(task_id, None) is not None

    async def close(self) -> None:
        return None


class SqliteTaskStore(TaskStore):
    """SQLite 持久任务存储（单机重启可查历史，本地可测）。"""

    def __init__(self, path: str = "data/tasks.sqlite3") -> None:
        self._path = path
        self._conn = None

    async def _db(self):
        import aiosqlite

        if self._conn is None:
            Path(self._path).parent.mkdir(parents=True, exist_ok=True)
            self._conn = await aiosqlite.connect(self._path)
            self._conn.row_factory = aiosqlite.Row
            await self._conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks(
                    task_id TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL,
                    task_input TEXT NOT NULL,
                    max_steps INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    tenant_id TEXT NOT NULL DEFAULT 'default',
                    result TEXT,
                    error TEXT,
                    events TEXT)""")
            await self._conn.commit()
        return self._conn

    async def create(self, task) -> None:
        await self.save(task)

    async def save(self, task) -> None:
        db = await self._db()
        rec = _record_to_dict(task)
        await db.execute(
            "INSERT OR REPLACE INTO tasks(task_id, thread_id, task_input, max_steps, status,"
            " created_at, tenant_id, result, error, events) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                rec["task_id"],
                rec["thread_id"],
                rec["task_input"],
                rec["max_steps"],
                rec["status"],
                rec["created_at"],
                rec.get("tenant_id", "default"),
                json.dumps(rec["result"], ensure_ascii=False, default=str),
                rec.get("error"),
                json.dumps(rec["events"], ensure_ascii=False, default=str),
            ),
        )
        await db.commit()

    @staticmethod
    def _row_to_record(row) -> dict:
        d = dict(row)
        if d.get("result"):
            d["result"] = json.loads(d["result"])
        if d.get("events"):
            d["events"] = json.loads(d["events"])
        return d

    async def get(self, task_id: str):
        db = await self._db()
        cur = await db.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,))
        row = await cur.fetchone()
        return _record_from_dict(self._row_to_record(row)) if row else None

    async def list(self, limit: int = 200) -> list:
        db = await self._db()
        cur = await db.execute("SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = await cur.fetchall()
        return [_record_from_dict(self._row_to_record(r)) for r in rows]

    async def delete(self, task_id: str) -> bool:
        db = await self._db()
        cur = await db.execute("DELETE FROM tasks WHERE task_id=?", (task_id,))
        await db.commit()
        return cur.rowcount > 0

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None


class RedisTaskStore(TaskStore):
    """Redis 任务存储（多实例共享，M5 上云默认）。

    未装 redis 依赖或连接失败 -> TaskStoreUnavailableError（fail-fast，不静默降级）。
    """

    _KEY_PREFIX = "flare:task:"

    def __init__(self, url: str = "redis://localhost:6379/0") -> None:
        self._url = url
        self._redis = None

    async def _client(self):
        if self._redis is None:
            try:
                import redis.asyncio as aioredis
            except ImportError as exc:
                raise TaskStoreUnavailableError("缺少 redis 依赖（pip install redis）") from exc
            self._redis = aioredis.from_url(self._url, decode_responses=True)
            try:
                await self._redis.ping()
            except Exception as exc:  # noqa: BLE001 - 连接失败统一转可用性错误
                await self._redis.aclose()
                self._redis = None
                raise TaskStoreUnavailableError(f"无法连接 Redis({self._url}): {exc}") from exc
        return self._redis

    def _key(self, task_id: str) -> str:
        return self._KEY_PREFIX + task_id

    async def create(self, task) -> None:
        await self.save(task)

    async def save(self, task) -> None:
        r = await self._client()
        await r.set(
            self._key(task.task_id),
            json.dumps(_record_to_dict(task), ensure_ascii=False, default=str),
        )

    async def get(self, task_id: str):
        r = await self._client()
        raw = await r.get(self._key(task_id))
        return _record_from_dict(json.loads(raw)) if raw else None

    async def list(self, limit: int = 200) -> list:
        r = await self._client()
        keys = await r.keys(self._KEY_PREFIX + "*")
        recs = []
        for k in keys[-limit:]:
            raw = await r.get(k)
            if raw:
                recs.append(_record_from_dict(json.loads(raw)))
        recs.sort(key=lambda t: t.created_at, reverse=True)
        return recs[:limit]

    async def delete(self, task_id: str) -> bool:
        r = await self._client()
        return (await r.delete(self._key(task_id))) > 0

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None
