"""任务 API（L1 真·流式）：POST 立即返回；SSE 实时推送；GET 详情/列表支持刷新恢复。

端到端回路：Web 发起任务（立即拿到 task_id）→ 后台执行 → SSE 实时看轨迹 → result 收尾（R6 硬目标）。
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

    @router.post("/tasks", status_code=202)
    async def create_task(body: TaskCreate) -> dict[str, Any]:
        task = await manager.create(
            body.task_input, thread_id=body.thread_id, max_steps=body.max_steps
        )
        return {"task_id": task.task_id, "thread_id": task.thread_id, "status": task.status}

    @router.get("/tasks")
    async def list_tasks() -> list[dict[str, Any]]:
        return [t.to_dict() for t in manager.recent()]

    @router.get("/tasks/{task_id}")
    async def get_task(task_id: str) -> dict[str, Any]:
        task = manager.get(task_id)
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
        task = manager.get(task_id)
        if task is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "NOT_FOUND", "message": f"任务不存在: {task_id}"},
            )
        return StreamingResponse(
            manager.stream(task),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return router
