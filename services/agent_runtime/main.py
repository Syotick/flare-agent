"""Agent Runtime 入口：make dev / uvicorn 从这里启动。

create_app() 保持纯 API（可测）；Web 构建产物(services/web/dist)在此挂到根路径，
未构建时则纯 API 模式（前端走 Vite dev 代理）。路径挂载放最后，避免遮蔽 API 路由。
知识库在 main 里落盘到 data/kb.sqlite3（跨重启复用；测试仍走内存库）。
"""

from __future__ import annotations

from pathlib import Path

from fastapi.staticfiles import StaticFiles

from agent_runtime.app import create_app
from rag.pipeline import KnowledgeBase
from rag.store import SqliteVectorStore

_kb_path = Path(__file__).resolve().parents[1] / "data" / "kb.sqlite3"
_kb_path.parent.mkdir(parents=True, exist_ok=True)

app = create_app(knowledge_base=KnowledgeBase(store=SqliteVectorStore(str(_kb_path))))

_web_dist = Path(__file__).resolve().parents[1] / "web" / "dist"
if _web_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(_web_dist), html=True), name="web")
