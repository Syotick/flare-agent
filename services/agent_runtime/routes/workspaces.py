"""工作区 API（DSH 对齐）。

- GET  /v1/workspaces            工作区聚合（id + 会话数 + 最近使用）
- GET  /v1/workspaces/dirs       目录浏览（对标 DSH host.listDirectory）
- POST /v1/workspaces/dirs       创建目录（对标 DSH host.createDirectory）

工作区 = 服务器（Host）上的真实目录路径：浏览器通过目录 API 浏览/创建目录，
选中路径作为 workspace_id，会话从属该目录工作区。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from agent_runtime.tasks import TaskManager
from agent_runtime.workspace_fs import create_directory, list_directory


class DirCreate(BaseModel):
    path: str = Field(min_length=1, max_length=1024)
    name: str = Field(min_length=1, max_length=128)


def build_workspaces_router(manager: TaskManager) -> APIRouter:
    router = APIRouter(prefix="/v1", tags=["workspaces"])

    @router.get("/workspaces")
    async def list_workspaces() -> list[dict[str, Any]]:
        """工作区列表：id + 会话数 + 最近使用时间（按最近使用倒序，含默认工作区）。"""
        return await manager.workspaces()

    @router.get("/workspaces/dirs")
    async def list_dirs(path: str | None = None) -> dict[str, Any]:
        """列目录（DSH host.listDirectory）：path 为空列出根级（Windows 盘符 / POSIX /）。"""
        return list_directory(path)

    @router.post("/workspaces/dirs", status_code=201)
    async def create_dir(body: DirCreate) -> dict[str, Any]:
        """在 path 下创建子目录（DSH host.createDirectory）；返回新目录绝对路径。"""
        return {"path": create_directory(body.path, body.name)}

    return router
