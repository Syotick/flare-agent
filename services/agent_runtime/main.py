"""Agent Runtime 入口：make dev / uvicorn 从这里启动。

create_app() 保持纯 API（可测）；Web 构建产物(services/web/dist)在此挂到根路径，
未构建时则纯 API 模式（前端走 Vite dev 代理）。路径挂载放最后，避免遮蔽 API 路由。
"""

from __future__ import annotations

from pathlib import Path

from fastapi.staticfiles import StaticFiles

from agent_runtime.app import create_app

app = create_app()

_web_dist = Path(__file__).resolve().parents[1] / "web" / "dist"
if _web_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(_web_dist), html=True), name="web")
