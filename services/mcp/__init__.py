"""MCP 客户端与网关（FR-2.2 / FR-2.3）。

- protocol.py：JSON-RPC 2.0 消息形状 + 方法常量 + 错误类型（零依赖）
- client.py：McpClient + 传输层（Streamable HTTP / SSE，httpx）
- adapter.py：MCP 工具 -> ToolRegistry.Tool（命名空间 mcp__<server>__<tool>）
- gateway.py：McpGateway（多服务器、白名单、认证头、审计、幂等注册）
- mcp_tools.py：mcp_connect / mcp_list 内置工具
- testing.py：测试用 FakeTransport + 最小真实 MCP Server（stdlib 零依赖）

开发默认不连任何服务器（FLARE_MCP_SERVERS 为空 -> 无行为变化）；
配置了服务器后按需连接（mcp_connect）或 strict 模式启动 fail-fast。
"""

from mcp.client import McpClient, build_transport
from mcp.gateway import McpGateway, McpServerConfig
from mcp.protocol import (
    McpConnectionError,
    McpError,
    McpProtocolError,
    McpToolError,
)
from mcp.testing import FakeTransport, MemoryMcpServer

__all__ = [
    "McpClient",
    "build_transport",
    "McpGateway",
    "McpServerConfig",
    "McpError",
    "McpConnectionError",
    "McpProtocolError",
    "McpToolError",
    "FakeTransport",
    "MemoryMcpServer",
]
