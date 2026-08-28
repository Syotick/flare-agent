"""FastAPI 应用工厂（create_app）。

无 import 副作用：创建时注入 settings，便于测试隔离与环境重建。
错误契约：FlareError -> {code, message, request_id}（A4）。
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from agent_runtime.routes.kb import build_kb_router
from agent_runtime.routes.memory import build_memory_router
from agent_runtime.routes.ops import build_ops_router
from agent_runtime.routes.tasks import build_tasks_router
from agent_runtime.task_store import (
    InMemoryTaskStore,
    RedisTaskStore,
    SqliteTaskStore,
    TaskStore,
)
from agent_runtime.tasks import TaskManager
from flare_common import __version__, metrics
from flare_common.config import Settings, get_settings
from flare_common.errors import FlareError
from flare_common.logging import setup_logging
from flare_common.otel import init_tracing
from flare_common.tenant import TenantMiddleware
from mcp.gateway import McpGateway, McpServerConfig
from mcp.mcp_tools import build_mcp_connect_tool, build_mcp_list_tool
from memory.mem_tools import build_memory_tools
from memory.memory import MemoryManager
from rag.kb_tools import build_kb_search_tool
from rag.pipeline import KnowledgeBase
from sandbox import build_sandbox
from skills.registry import SkillRegistry
from skills.skill_tools import build_skill_tools
from tools_gateway.builtin import create_default_registry

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


def _build_task_store(settings: Settings) -> TaskStore:
    """按配置选择任务存储（M5）：memory|sqlite|redis；未知值 fail-fast。"""
    if settings.task_store == "memory":
        return InMemoryTaskStore()
    if settings.task_store == "sqlite":
        return SqliteTaskStore("data/tasks.sqlite3")
    if settings.task_store == "redis":
        return RedisTaskStore(settings.redis_url)
    raise FlareError(f"未知 task_store: {settings.task_store!r}（应为 memory|sqlite|redis）")


def _build_mcp_gateway(settings: Settings) -> McpGateway:
    """按 FLARE_MCP_SERVERS 配置装配 MCP 网关（FR-2.3）。

    默认空列表 -> 网关无服务器（mcp_connect/mcp_list 工具返回"未配置"），无行为变化；
    配置了服务器 -> 工具按需连接（connect 非严格：连不上的服务器跳过并告警，
    connect_strict 严格模式供生产 fail-fast）。认证头由 McpServerConfig.headers 注入。
    """
    configs = [
        McpServerConfig(
            name=str(item["name"]),
            url=str(item["url"]),
            transport=str(item.get("transport", "streamable_http")),
            headers=dict(item.get("headers") or {}),
            tools=item.get("tools"),  # None=全部；[]=不注册
            enabled=bool(item.get("enabled", True)),
        )
        for item in settings.mcp_servers
    ]
    return McpGateway(configs)


def create_app(
    settings: Settings | None = None,
    task_manager: TaskManager | None = None,
    knowledge_base: KnowledgeBase | None = None,
    memory: MemoryManager | None = None,
) -> FastAPI:
    """创建 FastAPI 应用；注入 settings/task_manager/knowledge_base/memory 可隔离测试环境。

    未显式注入时：task_manager 使用默认注册表 + kb_search + mem_set/mem_recall 工具；
    knowledge_base 使用内存 SQLite + HashEmbedder，memory 使用内存事实库 + 向量库（开发默认）。
    """
    settings = settings or get_settings()
    setup_logging(settings.log_level)
    # M5：OTel 埋点（无端点 no-op；有端点且缺 SDK/导出失败 -> fail-fast）
    init_tracing(settings.app_name, settings.otel_endpoint or None)

    kb = knowledge_base
    mem = memory
    mcp_gateway: McpGateway | None = None
    if task_manager is None:
        if kb is None:
            kb = KnowledgeBase()  # 开发默认：内存 SQLite + HashEmbedder
        if mem is None:
            mem = MemoryManager()  # 开发默认：内存事实库 + 向量库
        sandbox = build_sandbox(settings)  # M4：开发=本地子进程；prod=容器(fail-fast 占位)
        registry = create_default_registry(sandbox=sandbox)
        registry.register(build_kb_search_tool(kb))
        for tool in build_memory_tools(mem):
            registry.register(tool)
        # FR-2/FR-3：MCP 网关 + 技能库（工具按需连接/加载；不阻塞启动）
        mcp_gateway = _build_mcp_gateway(settings)
        registry.register(build_mcp_connect_tool(mcp_gateway, registry))
        registry.register(build_mcp_list_tool(mcp_gateway))
        skill_registry = SkillRegistry(settings.skills_dir)
        for tool in build_skill_tools(skill_registry):
            registry.register(tool)
        task_manager = TaskManager(
            registry=registry,
            memory=mem,
            store=_build_task_store(settings),
        )

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        if mcp_gateway is not None:
            await mcp_gateway.close()  # FR-2.3：关闭 MCP 连接池
        if task_manager is not None:
            await task_manager.close()  # M4：关闭模型 HTTP 客户端等资源
        if kb is not None:
            await kb.close()
        if mem is not None:
            await mem.close()

    app = FastAPI(title=settings.app_name, version=__version__, lifespan=lifespan)
    app.add_middleware(TenantMiddleware)  # M5：X-Tenant-Id -> contextvar
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_exception_handler(FlareError, _flare_error_handler)
    app.add_exception_handler(Exception, _unhandled_error_handler)

    @app.middleware("http")
    async def _http_metrics(request: Request, call_next):
        """M6：HTTP 可观测性埋点（计数 + 耗时），/metrics 自身不计以免自刷。"""
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            metrics.observe_http(request.method, request.url.path, 500, time.perf_counter() - start)
            raise
        if not request.url.path.startswith("/metrics"):
            metrics.observe_http(
                request.method, request.url.path, response.status_code, time.perf_counter() - start
            )
        return response

    # M3a: 知识库 API（入库/列表/检索/删除）
    if kb is not None:
        app.include_router(build_kb_router(kb))

    # M3b: 记忆 API（长期事实 CRUD + 向量召回 + 上下文块）
    if mem is not None:
        app.include_router(build_memory_router(mem))

    # M2-4c: 任务 API（graph + checkpointer 接入 HTTP，端到端回路）
    app.include_router(build_tasks_router(task_manager))

    # M6: 运维 API（SLO 状态 / 错误预算）
    app.include_router(build_ops_router(settings))

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "env": settings.env}

    @app.get("/version", tags=["system"])
    async def version() -> dict[str, str]:
        return {"name": settings.app_name, "version": __version__}

    @app.get("/metrics", tags=["system"])
    async def metrics_endpoint() -> PlainTextResponse:
        """Prometheus 文本格式指标（M6）：被 HPA/Prometheus/压测采集。"""
        return PlainTextResponse(
            metrics.render_metrics(),
            media_type="text/plain; version=0.0.4",
        )

    return app
