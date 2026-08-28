"""MCP demo（FR-2.2/2.3）：进程内起一个真实 HTTP MCP Server，Agent 经 mcp_connect 接入。

运行（仓库根目录，conda env flare-agent）：
    PYTHONPATH=services python scripts/demo_mcp.py
"""

from __future__ import annotations

import asyncio

from mcp.gateway import McpGateway, McpServerConfig
from mcp.mcp_tools import build_mcp_connect_tool, build_mcp_list_tool
from mcp.testing import MemoryMcpServer
from tools_gateway.builtin import create_default_registry


async def main() -> None:
    server = MemoryMcpServer.with_defaults().start()
    print(f"[MCP Server] {server.url}（echo/add 工具）")
    try:
        gw = McpGateway([McpServerConfig(name="mem", url=server.url)])
        registry = create_default_registry()
        registry.register(build_mcp_connect_tool(gw, registry))
        registry.register(build_mcp_list_tool(gw))

        print("\n=== 连接前：注册表工具 ===")
        print([t.name for t in registry.list()])

        print("\n=== Agent 调 mcp_connect(name=mem) ===")
        print((await registry.execute("mcp_connect", {"name": "mem"})).content)

        print("\n=== 经注册表调用 MCP 工具 mcp__mem__add ===")
        print((await registry.execute("mcp__mem__add", {"a": 30, "b": 12})).content)

        print("\n=== mcp_list ===")
        print((await registry.execute("mcp_list", {})).content)
        await gw.close()
    finally:
        server.stop()


if __name__ == "__main__":
    asyncio.run(main())
