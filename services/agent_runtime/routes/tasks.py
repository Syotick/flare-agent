"""任务 API（M2-4c）：POST /v1/tasks 提交任务；GET /v1/tasks/{id}/stream SSE 回放轨迹。

端到端回路：Web 发起任务 → agent 调工具 → SSE 实时看执行轨迹 → 返回结果（R6 硬目标）。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agent_runtime.tasks import TaskManager


class TaskCreate(BaseModel):
    task_input: str = Field(min_length=1, max_length=10000)
    thread_id: str | None = None
    max_steps: int = Field(default=5, ge=1, le=50)


def build_tasks_router(manager: TaskManager) -> APIRouter:
    router = APIRouter(prefix="/v1", tags=["tasks"])

    @router.post("/tasks")
    async def create_task(body: TaskCreate) -> dict[str, Any]:
        task = await manager.create_and_run(
            body.task_input, thread_id=body.thread_id, max_steps=body.max_steps
        )
        return {
            "task_id": task.task_id,
            "thread_id": task.thread_id,
            "status": task.status,
            "result": task.result,
            "error": task.error,
        }

    @router.get("/tasks/{task_id}/stream")
    async def stream_task(task_id: str) -> StreamingResponse:
        task = manager.get(task_id)
        if task is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "NOT_FOUND", "message": f"任务不存在: {task_id}"},
            )
        return StreamingResponse(
            manager.to_sse(task),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return router
