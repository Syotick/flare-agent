"""MCP 客户端 + 网关 + 适配器测试（FR-2.2 / FR-2.3）。

覆盖：FakeTransport 单元路径 + 真实 HTTP（Streamable / SSE）集成路径 +
工具适配（命名空间）+ 网关（白名单/认证/审计/幂等注册）。
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from mcp.client import McpClient, _split_sse_events
from mcp.gateway import McpGateway, McpServerConfig
from mcp.mcp_tools import build_mcp_connect_tool, build_mcp_list_tool
from mcp.protocol import McpConnectionError, McpError, McpProtocolError, McpToolError
from mcp.testing import FakeTransport, MemoryMcpServer
from model_gateway.providers import LLMResponse, ToolCall, ToolCallDecision
from tools_gateway.builtin import create_default_registry
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


# ---------- Round 6 审查回归：M1-M7 ----------


class _SequenceMcpProvider:
    """模拟真实模型行为路径：mcp_connect -> mcp__mem__add -> 汇总（M1 回归）。

    首轮无工具观察 -> 调 mcp_connect；连接观察后 -> 调 mcp__mem__add（中途注册的工具）；
    add 观察后 -> final。验证"同任务内新注册工具对模型可见且可调用"（假接线修复）。
    """

    model = "seq"

    async def chat(self, messages, *, model=None, temperature=None, max_tokens=None, tools=None):
        last_tool = None
        for m in reversed(messages):
            if m.role == "tool":
                last_tool = m.content
                break
        if last_tool is None:
            decision = ToolCallDecision(
                action="call_tool", tool=ToolCall(name="mcp_connect", args={"name": "mem"})
            )
        elif last_tool.startswith("[mcp__mem__add]"):
            decision = ToolCallDecision(action="final", answer="汇总: " + last_tool)
        else:
            decision = ToolCallDecision(
                action="call_tool",
                tool=ToolCall(name="mcp__mem__add", args={"a": 30, "b": 12}),
            )
        return LLMResponse(content=decision.model_dump_json(), model="seq")

    async def stream(self, messages, *, model=None, temperature=None) -> AsyncIterator[str]:
        yield "."


async def test_sse_splitter_handles_cross_chunk():
    """M2 单元：SSE 增量切分只消费完整事件，半截事件保留在 buffer。"""
    ev, left = _split_sse_events("event: endpoi")
    assert ev == [] and left == "event: endpoi"
    ev, left = _split_sse_events(left + "nt\ndata: /message\n\n")
    assert ev == [("endpoint", "/message")] and left == ""
    ev, left = _split_sse_events('event: message\ndata: {"a":1}\n\nevent: messag')
    assert ev == [("message", '{"a":1}')]
    assert left == "event: messag"


@pytest.mark.asyncio
async def test_sse_real_server_cross_chunk():
    """M2 集成：真实 chunked 传输下事件跨 chunk 拆分，客户端仍能收到完整响应。

    修复前：endpoint 事件被拆分 -> 半截丢弃 -> _ready 永不 set -> 连接超时。
    """
    server = MemoryMcpServer.with_defaults().start(sse_chunk=True)
    try:
        client = McpClient(server.sse_url, transport_kind="sse", timeout=5.0)
        await client.connect()
        assert await client.call_tool("add", {"a": 20, "b": 22}) == "42"
        await client.close()
    finally:
        server.stop()


@pytest.mark.asyncio
async def test_react_graph_mcp_connect_mid_task_end_to_end():
    """M1 回归：Agent 中途 mcp_connect 注册的新工具，经 ReAct 图同任务内可调用。"""
    from langgraph.checkpoint.memory import MemorySaver

    from agent_runtime.graph import build_react_agent

    server = MemoryMcpServer.with_defaults().start()
    try:
        gw = McpGateway([McpServerConfig(name="mem", url=server.url)])
        registry = create_default_registry()
        registry.register(build_mcp_connect_tool(gw, registry))
        registry.register(build_mcp_list_tool(gw))
        agent = build_react_agent(
            _SequenceMcpProvider(), registry, max_steps=5, checkpointer=MemorySaver()
        )
        final = await agent.ainvoke(
            {"task_input": "用 MCP 工具算 30+12"},
            {"configurable": {"thread_id": "t-m1"}},
        )
        assert final.get("status") == "completed", final
        assert "42" in final.get("output", "")
        await gw.close()
    finally:
        server.stop()


async def test_gateway_register_all_filter():
    """M4：register_all(server_name=...) 只注册指定服务器，不触碰未连接的。"""
    gw = McpGateway(
        [
            McpServerConfig(name="a", url="http://fake", transport_impl=FakeTransport()),
            McpServerConfig(name="b", url="http://fake", transport_impl=FakeTransport()),
        ]
    )
    await gw.connect("a")
    registry = ToolRegistry()
    added = await gw.register_all(registry, server_name="a")
    assert added == ["mcp__a__echo", "mcp__a__add"]
    assert await gw.register_all(registry, server_name="b") == []  # b 未连接 -> 空，不报错
    await gw.close()


async def test_gateway_status_readonly():
    """M5：status() 只读快照（connected / tools_registered），不摸私有成员。"""
    gw = McpGateway(
        [McpServerConfig(name="mem", url="http://fake", transport_impl=FakeTransport())]
    )
    await gw.connect("mem")
    status = gw.status()
    assert status[0]["name"] == "mem" and status[0]["connected"] is True
    assert status[0]["tools_registered"] == []
    await gw.close()


async def test_gateway_audit_connect_and_register():
    """M6：连接与注册动作本身入审计（FR-2.3 所有 MCP 操作可审计）。"""
    audit: list[tuple] = []
    gw = McpGateway(
        [McpServerConfig(name="mem", url="http://fake", transport_impl=FakeTransport())],
        audit=lambda *a: audit.append(a),
    )
    await gw.connect("mem")
    registry = ToolRegistry()
    await gw.register_all(registry)
    assert any(a[0] == "connect" for a in audit), audit
    assert any(a[0] == "register" for a in audit), audit
    await gw.close()


async def test_adapter_truncates_long_output():
    """M7：MCP 工具长输出观察限长，完整内容进 artifacts（防撑爆上下文）。"""
    from mcp.adapter import OBSERVATION_LIMIT, make_mcp_tool

    transport = FakeTransport()
    original = transport.request

    async def patched(method, params):
        if method == "tools/call":
            return {"content": [{"type": "text", "text": "x" * (OBSERVATION_LIMIT + 500)}]}
        return await original(method, params)

    transport.request = patched  # type: ignore[method-assign]
    client = McpClient("http://fake", transport=transport)
    await client.connect()
    tool = make_mcp_tool(
        client,
        "mem",
        {
            "name": "echo",
            "description": "d",
            "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}},
        },
    )
    result = await tool.func(text="hi")
    assert result.ok is True
    assert "已截断" in result.content
    assert len(result.content) < OBSERVATION_LIMIT + 200
    assert "full_content" in result.artifacts
    assert len(result.artifacts["full_content"]) == OBSERVATION_LIMIT + 500
    await client.close()


@pytest.mark.asyncio
async def test_gateway_timeout_configurable_sse():
    """M3 回归：MCP 超时经配置传入传输层，慢服务器上的长任务按配置超时。"""
    import time as _time

    # 服务器对 tools/call 延迟 1s 产出 SSE 响应（202 已立即回，贴近真实流式服务器）
    server = MemoryMcpServer.with_defaults().start(sse_response_delay=1.0)
    try:
        gw = McpGateway(
            [McpServerConfig(name="mem", url=server.sse_url, transport="sse", timeout=0.3)]
        )
        await gw.connect("mem")
        t0 = _time.monotonic()
        res = await gw.call_tool("mem", "echo", {"text": "x"})
        dt = _time.monotonic() - t0
        assert res.ok is False and res.error_code == "MCP_CALL_ERROR"
        assert dt < 0.9, f"应按配置超时（实际 {dt:.2f}s）"
        await gw.close()
    finally:
        server.stop()
