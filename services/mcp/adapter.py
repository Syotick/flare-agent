"""MCP 工具适配：把 MCP Server 暴露的工具变成 ToolRegistry 的 Tool（FR-2.2 接线）。

命名：mcp__<server>__<tool> 前缀命名空间——MCP 工具来自外部命名空间，必须与内置工具
隔离（防撞名、防伪装）；参数：inputSchema（JSON Schema）直接作为 Tool.parameters，
复用 tools_gateway 的统一校验层（非法参数 422 契约不变）。

真理：外部工具的信任边界 = 网关层（白名单/认证/审计），工具本身视为不可信输入源，
适配时只做形状转换、不做特权放大——执行失败一律转结构化 ToolResult 回灌。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from mcp.client import McpClient
from mcp.protocol import McpError, McpToolError
from tools_gateway.registry import Tool, ToolResult

# 工具名命名空间前缀（mcp__<server>__<tool>）
NAMESPACE_PREFIX = "mcp__"

AuditFn = Callable[[str, str, str, dict[str, Any]], None]


def make_mcp_tool(
    client: McpClient,
    server_name: str,
    tool_spec: dict[str, Any],
    *,
    audit: AuditFn | None = None,
) -> Tool:
    """把一个 MCP 工具规格转成 ToolRegistry 的 Tool。

    - 名字带命名空间：mcp__{server_name}__{tool_name}
    - 执行：调 MCP call_tool，text content -> ToolResult.content；失败转结构化错误
    """
    tool_name = tool_spec["name"]
    full_name = f"{NAMESPACE_PREFIX}{server_name}__{tool_name}"
    description = str(
        tool_spec.get("description", "") or f"MCP 工具 {tool_name}（服务器 {server_name}）"
    )
    parameters = tool_spec.get("inputSchema") or {"type": "object", "properties": {}}
    if not isinstance(parameters, dict) or parameters.get("type") != "object":
        parameters = {"type": "object", "properties": {}}

    async def func(**kwargs: Any) -> ToolResult:
        if audit is not None:
            audit("call", server_name, tool_name, kwargs)
        try:
            content = await client.call_tool(tool_name, kwargs)
        except McpToolError as exc:
            return ToolResult(ok=False, error_code="MCP_TOOL_ERROR", content=str(exc))
        except McpError as exc:
            return ToolResult(ok=False, error_code="MCP_CALL_ERROR", content=str(exc))
        return ToolResult(ok=True, content=content)

    return Tool(name=full_name, description=description, parameters=parameters, func=func)


def mcp_tool_full_name(server_name: str, tool_name: str) -> str:
    return f"{NAMESPACE_PREFIX}{server_name}__{tool_name}"
