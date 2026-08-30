"""任务 API（L1 真·流式）：POST 立即返回；SSE 实时推送；GET 详情/列表支持刷新恢复。

端到端回路：Web 发起任务（立即拿到 task_id）→ 后台执行 → SSE 实时看轨迹 → result 收尾（R6 硬目标）。
"""

from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agent_runtime.tasks import TaskManager
from flare_common import metrics

logger = logging.getLogger("agent_runtime.tasks")


class TaskCreate(BaseModel):
    task_input: str = Field(min_length=1, max_length=10000)
    thread_id: str | None = None
    max_steps: int = Field(default=5, ge=1, le=50)
    # workspace_id 可为服务器真实目录路径（数百字符），上限放宽到 512
    workspace_id: str = Field(default="default", min_length=1, max_length=512)


def build_tasks_router(manager: TaskManager) -> APIRouter:
    router = APIRouter(prefix="/v1", tags=["tasks"])

    @router.post("/tasks", status_code=202)
    async def create_task(body: TaskCreate) -> dict[str, Any]:
        task = await manager.create(
            body.task_input,
            thread_id=body.thread_id,
            max_steps=body.max_steps,
            workspace_id=body.workspace_id,
        )
        return {
            "task_id": task.task_id,
            "thread_id": task.thread_id,
            "status": task.status,
            "workspace_id": task.workspace_id,
        }

    @router.get("/tasks")
    async def list_tasks(workspace: str | None = None) -> list[dict[str, Any]]:
        """会话列表；?workspace=<id> 时只返回该工作区会话（DSH 对齐：先选工作区再区分对话）。"""
        return [t.to_dict() for t in await manager.recent(workspace=workspace)]

    @router.get("/tasks/{task_id}")
    async def get_task(task_id: str) -> dict[str, Any]:
        task = await manager.get(task_id)
        if task is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "NOT_FOUND", "message": f"任务不存在: {task_id}"},
            )
        return task.to_dict()

    @router.delete("/tasks/{task_id}", status_code=204)
    async def delete_task(task_id: str) -> None:
        if not await manager.delete(task_id):
            raise HTTPException(
                status_code=404,
                detail={"code": "NOT_FOUND", "message": f"任务不存在: {task_id}"},
            )

    @router.get("/tasks/{task_id}/stream")
    async def stream_task(task_id: str) -> StreamingResponse:
        task = await manager.get(task_id)
        logger.info("SSE stream connect: task=%s exists=%s", task_id, task is not None)
        if task is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "NOT_FOUND", "message": f"任务不存在: {task_id}"},
            )

        async def _tracked_stream():
            """M6：流到终态后记录任务结果指标（成功率 + 端到端耗时）。"""
            started = time.monotonic()
            async for chunk in manager.stream(task):
                yield chunk
            outcome = "succeeded" if task.status == "completed" else "errored"
            metrics.observe_task(outcome, time.monotonic() - started)

        return StreamingResponse(
            _tracked_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return router
