"""MCP 网关内置工具（挂进 ToolRegistry，让 Agent 能按需拉取外部工具）。

- mcp_connect：连接已配置的 MCP 服务器并把其工具注册进注册表（幂等），
  Agent 调用后即可通过原生 function-calling 直接使用 mcp__<server>__<tool>。
- mcp_list：列出已配置服务器、连接状态、已注册工具（调试/教育用）。

真理：MCP 是"生态接入"——工具不在启动时全部强制注册，而是按需拉取
（可配 strict 模式在启动时 fail-fast）。这符合"外部依赖轻启动、用到了才连"。
"""

from __future__ import annotations

from typing import Any

from mcp.gateway import McpGateway
from tools_gateway.registry import Tool, ToolResult


def build_mcp_connect_tool(gateway: McpGateway, registry) -> Tool:
    async def _connect(**kwargs: Any) -> ToolResult:
        name = kwargs.get("name")
        if kwargs.get("strict"):
            await gateway.connect_strict()
        else:
            await gateway.connect(name)
        # M4-fix：只连接指定服务器时，register_all 也只注册该服务器（不遍历未连的）
        added = await gateway.register_all(registry, server_name=name)
        if not added:
            return ToolResult(
                ok=True,
                content="已连接 MCP 服务器，但无新工具注册（可能已全部注册或服务器无工具）",
            )
        return ToolResult(
            ok=True, content=f"已连接并注册 {len(added)} 个 MCP 工具: {', '.join(sorted(added))}"
        )

    return Tool(
        name="mcp_connect",
        description=(
            "连接配置的 MCP 服务器并把其工具注册到 Agent（幂等，可传 name 只连一个；"
            "strict=true 时任一服务器连不上即失败）。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "只连接该名称的服务器（省略=全部）"},
                "strict": {"type": "boolean", "description": "严格模式：任一服务器连接失败即报错"},
            },
        },
        func=_connect,
    )


def build_mcp_list_tool(gateway: McpGateway) -> Tool:
    async def _list(**kwargs: Any) -> ToolResult:
        status = gateway.status()  # M5-fix：只读接口，不摸网关私有成员
        if not status:
            return ToolResult(ok=True, content="未配置 MCP 服务器（FLARE_MCP_SERVERS 为空）")
        lines = []
        for s in status:
            lines.append(
                f"- {s['name']} [{s['transport']}] enabled={s['enabled']} "
                f"connected={s['connected']} tools_registered={len(s['tools_registered'])}"
            )
            for t in sorted(s["tools_registered"]):
                lines.append(f"    {t}")
        return ToolResult(ok=True, content=chr(10).join(lines))

    return Tool(
        name="mcp_list",
        description="列出已配置的 MCP 服务器、连接状态与已注册工具。",
        parameters={"type": "object", "properties": {}},
        func=_list,
    )
