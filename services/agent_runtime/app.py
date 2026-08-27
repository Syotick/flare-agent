"""FastAPI 应用工厂（create_app）。

无 import 副作用：创建时注入 settings，便于测试隔离与环境重建。
错误契约：FlareError -> {code, message, request_id}（A4）。
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from agent_runtime.routes.tasks import build_tasks_router
from agent_runtime.tasks import TaskManager
from flare_common import __version__
from flare_common.config import Settings, get_settings
from flare_common.errors import FlareError
from flare_common.logging import setup_logging

logger = logging.getLogger(__name__)


def _flare_error_handler(request: Request, exc: FlareError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.code,
            "message": exc.message or exc.code,
            "request_id": request.headers.get("X-Request-Id", ""),
        },
    )


async def _unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled error: %s", exc)
    return JSONResponse(
        status_code=500,
        content={
            "code": "INTERNAL_ERROR",
            "message": "internal error",
            "request_id": request.headers.get("X-Request-Id", ""),
        },
    )


def create_app(
    settings: Settings | None = None, task_manager: TaskManager | None = None
) -> FastAPI:
    """创建 FastAPI 应用；传入 settings/task_manager 可隔离测试环境。"""
    settings = settings or get_settings()
    setup_logging(settings.log_level)

    app = FastAPI(title=settings.app_name, version=__version__)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_exception_handler(FlareError, _flare_error_handler)
    app.add_exception_handler(Exception, _unhandled_error_handler)

    # M2-4c: 任务 API（graph + checkpointer 接入 HTTP，端到端回路）
    app.include_router(build_tasks_router(task_manager or TaskManager()))

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "env": settings.env}

    @app.get("/version", tags=["system"])
    async def version() -> dict[str, str]:
        return {"name": settings.app_name, "version": __version__}

    return app
