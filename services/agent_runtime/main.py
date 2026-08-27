"""Agent Runtime 入口（M2 最小骨架：系统端点）。

后续迭代：LangGraph 图 / 任务 API / SSE 流式 / checkpoint（见 02-module-design.md）。
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from common.config import get_settings
from common.logging import setup_logging

settings = get_settings()
setup_logging(settings.log_level)

app = FastAPI(title=settings.app_name, version="0.1.0")

# CORS：开发放开；生产收敛到 Web 域名白名单（M5 安全加固）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok", "env": settings.env}


@app.get("/version", tags=["system"])
async def version() -> dict[str, str]:
    return {"name": settings.app_name, "version": "0.1.0"}
