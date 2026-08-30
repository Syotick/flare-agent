"""工作区 API（DSH 对齐）：GET /v1/workspaces 聚合会话命名空间。

Web 先选工作区，再在工作区内新建对话——对话按工作区区分/隔离。
工作区 = 会话命名空间（TaskRecord.workspace_id），第一版聚焦会话隔离；
记忆（project_id）与知识库（全局）的按工作区隔离留待后续迭代。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from agent_runtime.tasks import TaskManager


def build_workspaces_router(manager: TaskManager) -> APIRouter:
    router = APIRouter(prefix="/v1", tags=["workspaces"])

    @router.get("/workspaces")
    async def list_workspaces() -> list[dict[str, Any]]:
        """工作区列表：id + 会话数 + 最近使用时间（按最近使用倒序，含默认工作区）。"""
        return await manager.workspaces()

    return router
