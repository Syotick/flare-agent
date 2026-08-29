"""审批 API（F1.3 人机协作）：列出待审批 / 查看详情 / 决策（批准|拒绝）。

审批请求由 agent loop 在敏感工具（F2.4 破坏性等）执行前通过 LangGraph interrupt 生成，
任务状态转 awaiting_approval；这里的人工决策 set 事件唤醒挂起的执行协程继续跑。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from agent_runtime.approval import ApprovalManager


class ApprovalDecision(BaseModel):
    approved: bool
    reason: str = Field(default="", max_length=500)
    decided_by: str = Field(default="", max_length=64)


def build_approval_router(manager: ApprovalManager) -> APIRouter:
    """构建审批路由（F1.3）。

    - manager: ApprovalManager（审批请求登记/决策/超时）
    """
    router = APIRouter(prefix="/v1/approvals", tags=["approvals"])

    def _missing() -> HTTPException:
        return HTTPException(
            status_code=404, detail={"code": "NOT_FOUND", "message": "审批请求不存在"}
        )

    @router.get("")
    async def list_approvals(pending_only: bool = False) -> list[dict[str, Any]]:
        requests = await manager.pending() if pending_only else await manager.list()
        return [r.to_dict() for r in requests]

    @router.get("/{approval_id}")
    async def get_approval(approval_id: str) -> dict[str, Any]:
        req = await manager.get(approval_id)
        if req is None:
            raise _missing()
        return req.to_dict()

    @router.post("/{approval_id}/decide")
    async def decide_approval(approval_id: str, body: ApprovalDecision) -> dict[str, Any]:
        if await manager.get(approval_id) is None:
            raise _missing()
        try:
            req = await manager.decide(
                approval_id,
                approved=body.approved,
                decided_by=body.decided_by,
                reason=body.reason,
            )
        except ValueError as exc:
            # 已处理的请求（如超时自动拒绝）重复决策 -> 409 冲突
            raise HTTPException(
                status_code=409,
                detail={"code": "ALREADY_DECIDED", "message": str(exc)},
            ) from exc
        return req.to_dict()

    return router
