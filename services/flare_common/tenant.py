"""多租户（M5）：请求头 X-Tenant-Id -> contextvar -> 各层作用域隔离。

- 缺省租户 "default"（单租户部署无需任何配置，行为不变）；
- TenantMiddleware 从请求头读租户并注入 contextvar，业务层 get_tenant_id() 即可拿；
- 任务/审计/配额都带 tenant_id；DB 级按 tenant_id 分表分区随 PG 迁移落地（见 migrate 脚本）。
"""

from __future__ import annotations

from contextvars import ContextVar

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

DEFAULT_TENANT = "default"
TENANT_HEADER = "X-Tenant-Id"

_tenant_var: ContextVar[str] = ContextVar("tenant_id", default=DEFAULT_TENANT)


def get_tenant_id() -> str:
    """取当前请求的租户（无请求上下文时返回 default）。"""
    return _tenant_var.get()


class TenantMiddleware(BaseHTTPMiddleware):
    """从请求头取租户注入 contextvar，并把租户回写响应头（便于排查）。"""

    async def dispatch(self, request: Request, call_next) -> Response:
        tenant = request.headers.get(TENANT_HEADER, DEFAULT_TENANT).strip() or DEFAULT_TENANT
        token = _tenant_var.set(tenant)
        try:
            response = await call_next(request)
            response.headers[TENANT_HEADER] = tenant
            return response
        finally:
            _tenant_var.reset(token)
