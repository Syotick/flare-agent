"""审批管理器（F1.3 人机协作 + F2.4 工具权限分级 + TOFU + 多实例后端）。

设计：
- 审批门是编排层的横切能力（与工具注册/执行解耦）：Tool 声明 permission 级别，
  策略（ApprovalPolicy）决定哪些工具要审批，图内工具执行前发 interrupt 挂起，
  ApprovalManager 登记请求并等待人工决策，决策后 resume 放行/拒绝。
- 后端抽象（ApprovalBackend）：Local（进程内 asyncio.Event，默认/单实例）与
  Redis（多实例共享，跨节点决策通过轮询唤醒，FLARE_APPROVAL_BACKEND=redis 启用）。
  超时（默认 300s）自动按拒绝处理，避免任务无限挂起。
- TOFU（Trust On First Use）：同一作用域（默认=会话线程）内某工具获批一次后，
  后续调用自动放行（免 interrupt），防审批疲劳；FLARE_APPROVAL_TOFU=false 关闭，
  FLARE_APPROVAL_TOFU_SCOPE=thread|tenant|off 控制信任作用域。

职责边界（防上帝模块）：
  只做"哪些工具要审批 + 请求登记/决策/超时/TOFU"；谁触发（图内 interrupt）、
  怎么呈现（Web 审批卡片/审批中心 API）都由上层负责。
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from flare_common.errors import FlareError
from tools_gateway.registry import PERMISSION_DESTRUCTIVE, PERMISSION_ORDER, Tool


class ApprovalBackendUnavailableError(FlareError):
    code = "APPROVAL_BACKEND_UNAVAILABLE"
    status_code = 503


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
    scope: str = ""  # TOFU 信任作用域（默认=会话线程 thread_id；tenant 则 tenant_id）

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
            "scope": self.scope,
        }


def _apply_decision(
    req: ApprovalRequest,
    *,
    approved: bool,
    decided_by: str = "",
    reason: str = "",
    status: str | None = None,
) -> None:
    """就地写入决策字段（Local/Redis 后端共用）。"""
    req.status = status or ("approved" if approved else "rejected")
    req.decided_at = time.time()
    req.decided_by = decided_by
    req.reason = reason


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


class ApprovalBackend:
    """审批后端协议：请求存取 + 决策 + 等待唤醒 + TOFU 信任集。

    Local：进程内（asyncio.Event 唤醒）；Redis：多实例共享（跨节点决策轮询唤醒）。
    """

    async def save(self, req: ApprovalRequest) -> None:
        """登记/更新请求（含决策状态写回）。"""
        raise NotImplementedError

    async def load(self, approval_id: str) -> ApprovalRequest | None:
        raise NotImplementedError

    async def decide(
        self,
        approval_id: str,
        *,
        approved: bool,
        decided_by: str = "",
        reason: str = "",
        status: str | None = None,
    ) -> ApprovalRequest:
        """人工/超时决策：写入决策并唤醒等待者；已处理请求抛 ValueError。"""
        raise NotImplementedError

    async def wait(self, approval_id: str, *, timeout: float) -> ApprovalRequest:
        """阻塞等待该请求被决策；超时自动按拒绝处理并返回。"""
        raise NotImplementedError

    async def pending(self) -> list[ApprovalRequest]:
        raise NotImplementedError

    async def list(self) -> list[ApprovalRequest]:
        raise NotImplementedError

    async def is_trusted(self, scope: str, tool_name: str) -> bool:
        raise NotImplementedError

    async def record_trust(self, scope: str, tool_name: str) -> None:
        raise NotImplementedError


class LocalApprovalBackend(ApprovalBackend):
    """进程内后端（默认）：请求在内存 + asyncio.Event 唤醒 + 信任集在内存。"""

    def __init__(self) -> None:
        self._requests: dict[str, ApprovalRequest] = {}
        self._events: dict[str, asyncio.Event] = {}
        self._trusted: dict[str, set[str]] = {}

    async def save(self, req: ApprovalRequest) -> None:
        self._requests[req.approval_id] = req
        self._events.setdefault(req.approval_id, asyncio.Event())

    async def load(self, approval_id: str) -> ApprovalRequest | None:
        return self._requests.get(approval_id)

    async def decide(
        self,
        approval_id: str,
        *,
        approved: bool,
        decided_by: str = "",
        reason: str = "",
        status: str | None = None,
    ) -> ApprovalRequest:
        req = self._requests.get(approval_id)
        if req is None:
            raise KeyError(f"未知审批请求: {approval_id}")
        if req.status != "pending":
            raise ValueError(f"审批请求已处理: {approval_id}（{req.status}）")
        _apply_decision(req, approved=approved, decided_by=decided_by, reason=reason, status=status)
        self._events[approval_id].set()
        return req

    async def wait(self, approval_id: str, *, timeout: float) -> ApprovalRequest:
        req = self._requests.get(approval_id)
        if req is None:
            raise KeyError(f"未知审批请求: {approval_id}")
        try:
            await asyncio.wait_for(self._events[approval_id].wait(), timeout=timeout)
        except TimeoutError:
            await self.decide(
                approval_id,
                approved=False,
                reason=f"审批超时（{timeout:.0f}s 未响应）",
                status="timed_out",
            )
        return self._requests[approval_id]

    async def pending(self) -> list[ApprovalRequest]:
        return [r for r in self._requests.values() if r.status == "pending"]

    async def list(self) -> list[ApprovalRequest]:
        return sorted(self._requests.values(), key=lambda r: r.requested_at)

    async def is_trusted(self, scope: str, tool_name: str) -> bool:
        return bool(scope) and tool_name in self._trusted.get(scope, set())

    async def record_trust(self, scope: str, tool_name: str) -> None:
        if scope:
            self._trusted.setdefault(scope, set()).add(tool_name)


class RedisApprovalBackend(ApprovalBackend):
    """Redis 后端（多实例共享）：请求存 hash + 待审批 set + 有序索引 + TOFU 信任 set。

    跨节点唤醒用轮询（wait 每 poll_interval 读一次状态，人类审批 200ms 感知延迟可忽略），
    免 pub/sub 生命周期管理；decide 在任意实例写 Redis，等待中的实例轮询到即醒。
    未装 redis 依赖或连接失败 -> ApprovalBackendUnavailableError（fail-fast，不静默降级）。
    """

    def __init__(
        self,
        redis=None,
        *,
        url: str = "redis://localhost:6379/0",
        prefix: str = "flare:approval",
        poll_interval: float = 0.2,
    ) -> None:
        self._redis = redis  # 注入对象（测试用）；None 则按 url 懒连接
        self._url = url
        self._prefix = prefix
        self._poll_interval = poll_interval

    def _key(self, approval_id: str) -> str:
        return f"{self._prefix}:req:{approval_id}"

    def _pending_key(self) -> str:
        return f"{self._prefix}:pending"

    def _index_key(self) -> str:
        return f"{self._prefix}:index"

    def _trusted_key(self, scope: str) -> str:
        return f"{self._prefix}:trusted:{scope}"

    async def _client(self):
        if self._redis is not None:
            return self._redis
        try:
            import redis.asyncio as aioredis
        except ImportError as exc:
            raise ApprovalBackendUnavailableError("缺少 redis 依赖（pip install redis）") from exc
        self._redis = aioredis.from_url(self._url, decode_responses=True)
        try:
            await self._redis.ping()
        except Exception as exc:  # noqa: BLE001 - 连接失败统一转可用性错误
            await self._redis.aclose()
            self._redis = None
            raise ApprovalBackendUnavailableError(f"无法连接 Redis({self._url}): {exc}") from exc
        return self._redis

    @staticmethod
    def _payload(req: ApprovalRequest) -> str:
        return json.dumps(req.to_dict(), ensure_ascii=False, default=str)

    async def save(self, req: ApprovalRequest) -> None:
        r = await self._client()
        await r.hset(self._key(req.approval_id), "payload", self._payload(req))
        await r.sadd(self._pending_key(), req.approval_id)
        await r.zadd(self._index_key(), {req.approval_id: req.requested_at})

    async def load(self, approval_id: str) -> ApprovalRequest | None:
        r = await self._client()
        raw = await r.hget(self._key(approval_id), "payload")
        if raw is None:
            return None
        return ApprovalRequest(**json.loads(raw))

    async def decide(
        self,
        approval_id: str,
        *,
        approved: bool,
        decided_by: str = "",
        reason: str = "",
        status: str | None = None,
    ) -> ApprovalRequest:
        req = await self.load(approval_id)
        if req is None:
            raise KeyError(f"未知审批请求: {approval_id}")
        if req.status != "pending":
            raise ValueError(f"审批请求已处理: {approval_id}（{req.status}）")
        _apply_decision(req, approved=approved, decided_by=decided_by, reason=reason, status=status)
        r = await self._client()
        await r.hset(self._key(approval_id), "payload", self._payload(req))
        await r.srem(self._pending_key(), approval_id)
        return req

    async def wait(self, approval_id: str, *, timeout: float) -> ApprovalRequest:
        """轮询等待：读到非 pending 即返回；超时自动按拒绝处理（timed_out）。"""
        deadline = time.monotonic() + timeout
        while True:
            req = await self.load(approval_id)
            if req is None:
                raise KeyError(f"未知审批请求: {approval_id}")
            if req.status != "pending":
                return req
            if time.monotonic() >= deadline:
                return await self.decide(
                    approval_id,
                    approved=False,
                    reason=f"审批超时（{timeout:.0f}s 未响应）",
                    status="timed_out",
                )
            await asyncio.sleep(self._poll_interval)

    async def pending(self) -> list[ApprovalRequest]:
        r = await self._client()
        ids = await r.smembers(self._pending_key())
        out: list[ApprovalRequest] = []
        for aid in ids:
            req = await self.load(aid)
            if req is not None and req.status == "pending":
                out.append(req)
        return out

    async def list(self) -> list[ApprovalRequest]:
        r = await self._client()
        ids = await r.zrange(self._index_key(), 0, -1)
        out: list[ApprovalRequest] = []
        for aid in ids:
            req = await self.load(aid)
            if req is not None:
                out.append(req)
        return out

    async def is_trusted(self, scope: str, tool_name: str) -> bool:
        if not scope:
            return False
        r = await self._client()
        return bool(await r.sismember(self._trusted_key(scope), tool_name))

    async def record_trust(self, scope: str, tool_name: str) -> None:
        if not scope:
            return
        r = await self._client()
        await r.sadd(self._trusted_key(scope), tool_name)


class ApprovalManager:
    """审批管理器：策略 + 后端（Local/Redis）+ TOFU（首用信任）。"""

    def __init__(
        self,
        policy: ApprovalPolicy | None = None,
        *,
        timeout: float = 300.0,
        backend: ApprovalBackend | None = None,
        tofu_enabled: bool = True,
        tofu_scope: str = "thread",
    ) -> None:
        self._policy = policy or ApprovalPolicy()
        self._timeout = timeout
        self._backend = backend or LocalApprovalBackend()
        if tofu_scope not in ("thread", "tenant", "off"):
            raise ValueError(f"未知 TOFU 作用域: {tofu_scope!r}（应为 thread|tenant|off）")
        self._tofu_enabled = tofu_enabled
        self._tofu_scope = tofu_scope

    @property
    def policy(self) -> ApprovalPolicy:
        return self._policy

    @property
    def backend(self) -> ApprovalBackend:
        return self._backend

    @property
    def tofu_scope(self) -> str:
        return self._tofu_scope

    def scope_for(self, thread_id: str, tenant_id: str = "default") -> str | None:
        """按 TOFU 作用域算信任键（thread=会话线程 / tenant=租户 / off=None=不信任）。"""
        if not self._tofu_enabled or self._tofu_scope == "off":
            return None
        return tenant_id if self._tofu_scope == "tenant" else thread_id

    async def requires_approval(self, tool: Tool, *, scope: str | None = None) -> bool:
        """F2.4：该工具是否需要人工审批（图内工具执行前调用）。

        TOFU：策略要求审批但该作用域已信任此工具 -> 放行（免 interrupt）。
        """
        trusted = (
            self._tofu_enabled
            and scope is not None
            and await self._backend.is_trusted(scope, tool.name)
        )
        return self._policy.requires_approval(tool) and not trusted

    async def _maybe_record_trust(self, req: ApprovalRequest) -> None:
        """TOFU 开且该请求获批 -> 记录信任（决策与超时唤醒两个路径共用）。"""
        if self._tofu_enabled and req.status == "approved" and req.scope:
            await self._backend.record_trust(req.scope, req.tool_name)

    async def register(
        self,
        task_id: str,
        tool_name: str,
        args: dict[str, Any],
        *,
        permission: str = PERMISSION_DESTRUCTIVE,
        description: str = "",
        scope: str | None = None,
    ) -> ApprovalRequest:
        """登记一条待审批请求（供 REST 决策 / 前端展示），返回带 approval_id 的记录。"""
        req = ApprovalRequest(
            approval_id=uuid.uuid4().hex[:12],
            task_id=task_id,
            tool_name=tool_name,
            args=dict(args or {}),
            permission=permission,
            description=description,
            scope=scope or "",
        )
        await self._backend.save(req)
        return req

    async def wait(self, approval_id: str) -> dict[str, Any]:
        """阻塞等待该请求的人工决策；超时自动按拒绝处理（不无限挂起）。

        返回 {"approved": bool, "reason": str}，供图 resume 使用。
        """
        req = await self._backend.wait(approval_id, timeout=self._timeout)
        await self._maybe_record_trust(req)
        return {"approved": req.status == "approved", "reason": req.reason}

    async def decide(
        self,
        approval_id: str,
        *,
        approved: bool,
        decided_by: str = "",
        reason: str = "",
    ) -> ApprovalRequest:
        """人工决策（REST 端点调用）：写入决策并唤醒等待中的执行协程。"""
        req = await self._backend.decide(
            approval_id,
            approved=approved,
            decided_by=decided_by,
            reason=reason,
        )
        await self._maybe_record_trust(req)
        return req

    async def get(self, approval_id: str) -> ApprovalRequest | None:
        return await self._backend.load(approval_id)

    async def pending(self) -> list[ApprovalRequest]:
        return await self._backend.pending()

    async def list(self) -> list[ApprovalRequest]:
        return await self._backend.list()
