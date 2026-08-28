"""MCP 网关（FR-2.3）：统一管理多个 MCP Server 连接，做白名单/认证/审计。

职责边界（防上帝模块）：
  - 连接生命周期：connect_all / close（多个 McpClient）
  - 安全控制：服务器级白名单（allowed_servers）+ 认证头注入 + 工具调用审计
  - 工具接线：register_all 把各服务器工具适配进 ToolRegistry（幂等）
  - 禁止 Agent 直连外部 server：所有调用都必须经过网关（FR-2.3 原文）

限流/配额随 M5/M6 在此层继续扩展（目前记录审计钩子，供上层注入）。
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from mcp.adapter import make_mcp_tool
from mcp.client import McpClient, McpTransport
from mcp.protocol import McpConnectionError, McpError
from tools_gateway.registry import ToolRegistry, ToolResult

logger = logging.getLogger(__name__)

AuditFn = Callable[[str, str, str, dict[str, Any]], None]


@dataclass
class McpServerConfig:
    """一个 MCP Server 的连接配置（来自 FLARE_MCP_SERVERS 或测试注入）。

    - name: 网关内唯一名（工具命名空间 mcp__<name>__<tool>）
    - url: 服务器地址
    - transport: streamable_http | sse
    - headers: 认证/自定义头（如 Authorization: Bearer xxx）
    - tools: 可选工具白名单（None=全部）；调用/注册只放行名单内工具（FR-2.3）
    - enabled: 是否参与本次 connect_all
    """

    name: str
    url: str
    transport: str = "streamable_http"  # streamable_http | sse（json 配置的 transport）
    headers: dict[str, str] = field(default_factory=dict)
    tools: list[str] | None = None  # None=允许全部；[]=不注册任何工具
    enabled: bool = True
    transport_impl: McpTransport | None = None  # 测试/定制注入的传输实现（默认按 transport 构造）


class McpGateway:
    """多服务器 MCP 网关。"""

    def __init__(
        self,
        configs: list[McpServerConfig],
        *,
        allowed_servers: set[str] | None = None,
        audit: AuditFn | None = None,
    ) -> None:
        self._configs = {c.name: c for c in configs}
        self._allowed = allowed_servers  # None=不限制（仅配置内）
        self._audit = audit
        self._clients: dict[str, McpClient] = {}
        self._registered: set[str] = set()
        self._registered_tools: dict[str, list[str]] = {}

    # --- 连接生命周期 ---

    async def connect(self, name: str | None = None) -> list[str]:
        """连接指定（或全部 enabled）服务器；返回成功连接名列表。

        服务器不可达 -> 该服务器失败（记日志并继续其余），调用方按需 fail-fast。
        """
        targets = [name] if name else list(self._configs)
        connected: list[str] = []
        for n in targets:
            cfg = self._configs.get(n)
            if cfg is None:
                raise McpConnectionError(f"未知 MCP 服务器: {n}")
            if not cfg.enabled:
                continue
            if n in self._clients:
                connected.append(n)
                continue
            client = self._make_client(cfg)
            try:
                await client.connect()
            except McpError as exc:
                logger.warning("MCP 服务器 %s 连接失败: %s", n, exc)
                continue
            self._clients[n] = client
            connected.append(n)
        return connected

    async def connect_strict(self) -> None:
        """严格模式：任一 enabled 服务器连不上 -> 抛错（生产 fail-fast）。"""
        failed: list[str] = []
        targets = [n for n, c in self._configs.items() if c.enabled]
        for n in targets:
            cfg = self._configs[n]
            if n in self._clients:
                continue
            client = self._make_client(cfg)
            try:
                await client.connect()
            except McpError as exc:
                failed.append(f"{n}: {exc}")
                continue
            self._clients[n] = client
        if failed:
            raise McpConnectionError("MCP 连接失败: " + "; ".join(failed))

    def _make_client(self, cfg: McpServerConfig) -> McpClient:
        """构造客户端：优先用注入的 transport_impl（测试），否则按 transport 类型构造。"""
        if cfg.transport_impl is not None:
            return McpClient(cfg.url, transport=cfg.transport_impl, headers=cfg.headers or None)
        return McpClient(cfg.url, transport_kind=cfg.transport, headers=cfg.headers or None)

    def is_allowed(self, server_name: str) -> bool:
        """服务器级白名单（FR-2.3）：未列入白名单的服务器直接拒绝。"""
        if self._allowed is None:
            return True
        return server_name in self._allowed

    # --- 工具清单与调用 ---

    async def list_tools(self, server_name: str) -> list[dict[str, Any]]:
        if not self.is_allowed(server_name):
            raise McpConnectionError(f"MCP 服务器未在白名单: {server_name}")
        client = self._clients.get(server_name)
        if client is None:
            raise McpConnectionError(f"MCP 服务器未连接: {server_name}")
        tools = await client.list_tools()
        cfg = self._configs[server_name]
        if cfg.tools is not None:
            tools = [t for t in tools if t.get("name") in cfg.tools]
        return tools

    async def register_all(self, registry: ToolRegistry) -> list[str]:
        """把各服务器工具适配注册进 ToolRegistry（幂等，返回新增工具名）。"""
        registered: list[str] = []
        for name in self._configs:
            if not self._configs[name].enabled or not self.is_allowed(name):
                continue
            try:
                tools = await self.list_tools(name)
            except McpError as exc:
                logger.warning("MCP %s 工具拉取失败: %s", name, exc)
                continue
            added = self._register_one(registry, name, tools)
            registered.extend(added)
        return registered

    def _register_one(
        self, registry: ToolRegistry, server_name: str, tools: list[dict[str, Any]]
    ) -> list[str]:
        client = self._clients[server_name]
        added: list[str] = []
        recorded = self._registered_tools.setdefault(server_name, [])
        for spec in tools:
            full_name = f"mcp__{server_name}__{spec.get('name')}"
            if full_name in self._registered:
                continue
            tool = make_mcp_tool(client, server_name, spec, audit=self._audit)
            try:
                registry.register(tool)
            except ValueError:
                continue  # 撞名（理论上不会，命名空间已隔离）——跳过不炸
            self._registered.add(full_name)
            recorded.append(full_name)
            added.append(full_name)
        return added

    async def call_tool(self, server_name: str, tool_name: str, args: dict[str, Any]) -> ToolResult:
        """经网关调用工具（FR-2.3：禁止 Agent 直连，统一走网关）。"""
        if not self.is_allowed(server_name):
            return ToolResult(
                ok=False, error_code="MCP_FORBIDDEN", content=f"服务器未在白名单: {server_name}"
            )
        client = self._clients.get(server_name)
        if client is None:
            return ToolResult(
                ok=False, error_code="MCP_NOT_CONNECTED", content=f"服务器未连接: {server_name}"
            )
        if self._audit is not None:
            self._audit("call", server_name, tool_name, args)
        try:
            content = await client.call_tool(tool_name, args)
        except McpError as exc:
            return ToolResult(ok=False, error_code="MCP_CALL_ERROR", content=str(exc))
        return ToolResult(ok=True, content=content)

    async def close(self) -> None:
        for client in self._clients.values():
            await client.close()
        self._clients.clear()
