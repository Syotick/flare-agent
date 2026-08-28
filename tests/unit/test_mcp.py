"""MCP 客户端 + 网关 + 适配器测试（FR-2.2 / FR-2.3）。

覆盖：FakeTransport 单元路径 + 真实 HTTP（Streamable / SSE）集成路径 +
工具适配（命名空间）+ 网关（白名单/认证/审计/幂等注册）。
"""

from __future__ import annotations

import pytest

from mcp.client import McpClient
from mcp.gateway import McpGateway, McpServerConfig
from mcp.protocol import McpConnectionError, McpError, McpProtocolError, McpToolError
from mcp.testing import FakeTransport, MemoryMcpServer
from tools_gateway.registry import ToolRegistry


def make_client(**kw) -> McpClient:
    return McpClient("http://fake", transport=FakeTransport(), **kw)


async def test_fake_connect_list_and_call():
    client = make_client()
    await client.connect()
    assert client.connected is True
    tools = await client.list_tools()
    assert [t["name"] for t in tools] == ["echo", "add"]
    assert await client.call_tool("echo", {"text": "hi"}) == "echo: hi"
    assert await client.call_tool("add", {"a": 2, "b": 3}) == "5"
    await client.close()
    assert client.connected is False


async def test_initialize_failure_fails_fast():
    client = McpClient("http://fake", transport=FakeTransport(fail_initialize=True))
    with pytest.raises(McpConnectionError):
        await client.connect()
    assert client.connected is False


async def test_tools_cached_and_force_refresh():
    transport = FakeTransport()
    client = McpClient("http://fake", transport=transport)
    await client.connect()
    await client.list_tools()
    n1 = transport.request_count
    await client.list_tools()
    assert transport.request_count == n1, "未 force 时应走缓存"
    await client.list_tools(force=True)
    assert transport.request_count == n1 + 1
    await client.close()


async def test_tool_execution_error_mapping():
    # 服务器报"未知工具" -> McpError（协议层错误，非工具结果）
    client = make_client()
    await client.connect()
    with pytest.raises(McpError):
        await client.call_tool("no_such", {})
    await client.close()


async def test_iserror_maps_to_mcptoolerror():
    transport = FakeTransport()
    original = transport.request

    async def patched(method, params):
        if method == "tools/call":
            return {"content": [{"type": "text", "text": "boom"}], "isError": True}
        return await original(method, params)

    transport.request = patched  # type: ignore[method-assign]
    client = McpClient("http://fake", transport=transport)
    await client.connect()
    with pytest.raises(McpToolError):
        await client.call_tool("echo", {})
    await client.close()


@pytest.mark.asyncio
async def test_streamable_http_real_server():
    server = MemoryMcpServer.with_defaults().start()
    try:
        client = McpClient(server.url)
        await client.connect()
        tools = await client.list_tools()
        assert [t["name"] for t in tools] == ["echo", "add"]
        assert await client.call_tool("add", {"a": 20, "b": 22}) == "42"
        await client.close()
    finally:
        server.stop()


@pytest.mark.asyncio
async def test_sse_real_server():
    server = MemoryMcpServer.with_defaults().start()
    try:
        client = McpClient(server.sse_url, transport_kind="sse")
        await client.connect()
        assert await client.call_tool("echo", {"text": "sse"}) == "echo: sse"
        await client.close()
    finally:
        server.stop()


async def test_adapter_registers_namespaced_tool():
    from mcp.adapter import make_mcp_tool

    registry = ToolRegistry()
    client = make_client()
    await client.connect()
    for spec in await client.list_tools():
        registry.register(make_mcp_tool(client, "mem", spec))
    await client.close()
    names = [t.name for t in registry.list()]
    assert "mcp__mem__echo" in names and "mcp__mem__add" in names
    result = await registry.execute("mcp__mem__add", {"a": 1, "b": 2})
    assert result.ok is True and result.content == "3"


async def test_gateway_allowlist_and_audit():
    audit: list[tuple] = []
    gw = McpGateway(
        [McpServerConfig(name="mem", url="http://fake", transport_impl=FakeTransport())],
        allowed_servers={"mem"},
        audit=lambda *a: audit.append(a),
    )
    await gw.connect("mem")
    registry = ToolRegistry()
    added = await gw.register_all(registry)
    assert len(added) == 2
    # 幂等：再注册不重复
    added2 = await gw.register_all(registry)
    assert added2 == []
    result = await gw.call_tool("mem", "echo", {"text": "via gateway"})
    assert result.ok is True and result.content == "echo: via gateway"
    assert any(a[0] == "call" and a[2] == "echo" for a in audit), audit
    await gw.close()


async def test_gateway_forbidden_server():
    gw = McpGateway(
        [McpServerConfig(name="mem", url="http://fake", transport_impl=FakeTransport())],
        allowed_servers={"other"},  # mem 不在白名单
    )
    result = await gw.call_tool("mem", "echo", {})
    assert result.ok is False and result.error_code == "MCP_FORBIDDEN"
    await gw.close()


async def test_gateway_tool_whitelist_per_server():
    gw = McpGateway(
        [
            McpServerConfig(
                name="mem", url="http://fake", tools=["echo"], transport_impl=FakeTransport()
            )
        ]
    )
    await gw.connect("mem")
    tools = await gw.list_tools("mem")
    assert [t["name"] for t in tools] == ["echo"], "tools 白名单应只放行 echo"
    await gw.close()


async def test_parse_response_protocol_errors():
    from mcp.protocol import parse_response

    with pytest.raises(McpProtocolError):
        parse_response({"jsonrpc": "2.0", "id": 1})  # 无 result 无 error
    with pytest.raises(McpProtocolError):
        parse_response("not a dict")
    with pytest.raises(McpError):
        parse_response({"jsonrpc": "2.0", "id": 1, "error": {"code": -32601, "message": "nf"}})
    assert parse_response({"jsonrpc": "2.0", "id": 1, "result": {"ok": 1}}) == {"ok": 1}


@pytest.mark.asyncio
async def test_mcp_connect_tool_end_to_end_real_http():
    """端到端：Agent 经 mcp_connect 拉取真实 HTTP 服务器的工具并调用。"""
    from mcp.mcp_tools import build_mcp_connect_tool, build_mcp_list_tool

    server = MemoryMcpServer.with_defaults().start()
    try:
        gw = McpGateway([McpServerConfig(name="mem", url=server.url)])
        registry = ToolRegistry()
        registry.register(build_mcp_connect_tool(gw, registry))
        registry.register(build_mcp_list_tool(gw))
        names = [t.name for t in registry.list()]
        assert "mcp__mem__echo" not in names, "连接前不应注册 MCP 工具"
        # Agent 调 mcp_connect -> 注册 MCP 工具（走真实 HTTP）
        res = await registry.execute("mcp_connect", {"name": "mem"})
        assert res.ok, res.content
        names = [t.name for t in registry.list()]
        assert "mcp__mem__echo" in names and "mcp__mem__add" in names
        # 幂等：再次 connect 不重复注册
        res2 = await registry.execute("mcp_connect", {})
        assert res2.ok is True
        # 经注册表调用 MCP 工具
        r = await registry.execute("mcp__mem__add", {"a": 7, "b": 5})
        assert r.ok is True and r.content == "12"
        lst = await registry.execute("mcp_list", {})
        assert lst.ok is True and "mem" in lst.content
        await gw.close()
    finally:
        server.stop()
