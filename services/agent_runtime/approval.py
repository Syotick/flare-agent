"""审批管理器（F1.3 人机协作 + F2.4 工具权限分级）。

设计：
- 审批门是编排层的横切能力（与工具注册/执行解耦）：Tool 声明 permission 级别，
  策略（ApprovalPolicy）决定哪些工具要审批，图内工具执行前发 interrupt 挂起，
  ApprovalManager 登记请求并阻塞等待人工决策，决策后 resume 放行/拒绝。
- 等待用 asyncio.Event：决策 REST 端点 set 事件唤醒挂起的执行协程；
  超时（默认 300s）自动按拒绝处理，避免任务无限挂起。
- 单进程实现（事件在进程内）；多实例/跨节点审批随 M5 上 Redis 演进（TODO）。

职责边界（防上帝模块）：
  只做"哪些工具要审批 + 请求登记/决策/超时"；谁触发（图内 interrupt）、
  怎么呈现（Web 审批卡片/API）都由上层负责。
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from tools_gateway.registry import PERMISSION_DESTRUCTIVE, PERMISSION_ORDER, Tool


@dataclass
class ApprovalRequest:
    """一条待人工审批的敏感操作请求。"""

    approval_id: str
    task_id: str
    tool_name: str
    args: dict[str, Any]
    permission: str
    description: str = ""
    status: str = "pending"  # pending | approved | rejected | timed_out
    requested_at: float = field(default_factory=time.time)
    decided_at: float | None = None
    decided_by: str = ""
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "approval_id": self.approval_id,
            "task_id": self.task_id,
            "tool_name": self.tool_name,
            "args": self.args,
            "permission": self.permission,
            "description": self.description,
            "status": self.status,
            "requested_at": self.requested_at,
            "decided_at": self.decided_at,
            "decided_by": self.decided_by,
            "reason": self.reason,
        }


class ApprovalPolicy:
    """审批策略：默认等于或高于 require_level 的工具需审批；可追加工具名白名单。

    默认 require_level=destructive：只有破坏性工具（如 sandbox_run）需要审批，
    read/write 工具放行（无行为变化，向后兼容）。
    """

    def __init__(
        self,
        require_level: str = PERMISSION_DESTRUCTIVE,
        extra_tools: set[str] | None = None,
    ) -> None:
        if require_level not in PERMISSION_ORDER:
            raise ValueError(f"未知权限级别: {require_level!r}（应为 {sorted(PERMISSION_ORDER)}）")
        self._require_rank = PERMISSION_ORDER[require_level]
        self._extra = set(extra_tools or [])

    def requires_approval(self, tool: Tool) -> bool:
        if tool.name in self._extra:
            return True
        return PERMISSION_ORDER.get(tool.permission, 0) >= self._require_rank


class ApprovalManager:
    """审批管理器：登记请求 + 等待人工决策（事件唤醒/超时自动拒绝）。"""

    def __init__(
        self,
        policy: ApprovalPolicy | None = None,
        *,
        timeout: float = 300.0,
    ) -> None:
        self._policy = policy or ApprovalPolicy()
        self._timeout = timeout
        self._requests: dict[str, ApprovalRequest] = {}
        self._events: dict[str, asyncio.Event] = {}

    @property
    def policy(self) -> ApprovalPolicy:
        return self._policy

    def requires_approval(self, tool: Tool) -> bool:
        """F2.4：该工具是否需要人工审批（图内工具执行前调用）。"""
        return self._policy.requires_approval(tool)

    def register(
        self,
        task_id: str,
        tool_name: str,
        args: dict[str, Any],
        *,
        permission: str = PERMISSION_DESTRUCTIVE,
        description: str = "",
    ) -> ApprovalRequest:
        """登记一条待审批请求（供 REST 决策 / 前端展示），返回带 approval_id 的记录。"""
        req = ApprovalRequest(
            approval_id=uuid.uuid4().hex[:12],
            task_id=task_id,
            tool_name=tool_name,
            args=dict(args or {}),
            permission=permission,
            description=description,
        )
        self._requests[req.approval_id] = req
        self._events[req.approval_id] = asyncio.Event()
        return req

    async def wait(self, approval_id: str) -> dict[str, Any]:
        """阻塞等待该请求的人工决策；超时自动按拒绝处理（不无限挂起）。

        返回 {"approved": bool, "reason": str}，供图 resume 使用。
        """
        req = self._requests.get(approval_id)
        if req is None:
            raise KeyError(f"未知审批请求: {approval_id}")
        ev = self._events[approval_id]
        try:
            await asyncio.wait_for(ev.wait(), timeout=self._timeout)
        except TimeoutError:
            self._decide(
                approval_id,
                approved=False,
                reason=f"审批超时（{self._timeout:.0f}s 未响应）",
                status="timed_out",
            )
        return {"approved": req.status == "approved", "reason": req.reason}

    def decide(
        self,
        approval_id: str,
        *,
        approved: bool,
        decided_by: str = "",
        reason: str = "",
    ) -> ApprovalRequest:
        """人工决策（REST 端点调用）：设置决策并唤醒等待中的执行协程。"""
        req = self._requests.get(approval_id)
        if req is None:
            raise KeyError(f"未知审批请求: {approval_id}")
        if req.status != "pending":
            raise ValueError(f"审批请求已处理: {approval_id}（{req.status}）")
        self._decide(approval_id, approved=approved, decided_by=decided_by, reason=reason)
        return req

    def _decide(
        self,
        approval_id: str,
        *,
        approved: bool,
        decided_by: str = "",
        reason: str = "",
        status: str | None = None,
    ) -> None:
        req = self._requests[approval_id]
        req.status = status or ("approved" if approved else "rejected")
        req.decided_at = time.time()
        req.decided_by = decided_by
        req.reason = reason
        ev = self._events.get(approval_id)
        if ev is not None:
            ev.set()

    def get(self, approval_id: str) -> ApprovalRequest | None:
        return self._requests.get(approval_id)

    def pending(self) -> list[ApprovalRequest]:
        return [r for r in self._requests.values() if r.status == "pending"]

    def list(self) -> list[ApprovalRequest]:
        return sorted(self._requests.values(), key=lambda r: r.requested_at)
