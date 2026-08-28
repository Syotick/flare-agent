"""MCP 客户端（FR-2.2）：连接一个 MCP Server 并暴露其工具。

McpClient 封装与一个 MCP Server 的完整生命周期：
  connect()    -> initialize 握手 + notifications/initialized
  list_tools() -> tools/list -> [{name, description, inputSchema}]
  call_tool(name, args) -> 提取 text content；服务器 isError -> McpToolError
  close()

传输层抽象 McpTransport（协议层在 protocol.py，传输可插拔）：
  - StreamableHttpTransport：现代标准（POST JSON-RPC，单响应或 SSE 流）
  - SseTransport：HTTP+SSE 经典形态（GET 事件流发现 endpoint，POST 消息）
测试用 FakeTransport（mcp/testing.py），真实链路用 stdlib HTTP 集成测试。

真理：MCP 连接是"先握手再干活"——不经过 initialize 的客户端直接 tools/list
属于未定义行为；握手失败必须显式抛错（fail-fast），不静默当"无工具"。
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from typing import Any, Protocol
from urllib.parse import urljoin

import httpx

from mcp.protocol import (
    CLIENT_NAME,
    METHOD_INITIALIZE,
    METHOD_INITIALIZED,
    METHOD_TOOLS_CALL,
    METHOD_TOOLS_LIST,
    PROTOCOL_VERSION,
    McpConnectionError,
    McpError,
    McpProtocolError,
    McpToolError,
    build_notification,
    build_request,
    extract_text_content,
    parse_response,
)

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 10.0


class McpTransport(Protocol):
    """传输层抽象：只负责把 JSON-RPC 请求送出去、把结果拿回来。"""

    async def connect(self) -> None: ...

    async def request(self, method: str, params: dict[str, Any] | None) -> dict[str, Any]:
        """发一个带 id 的请求，返回服务器 result dict（失败抛 McpError）。"""
        ...

    async def notify(self, method: str, params: dict[str, Any] | None) -> None:
        """发一个通知（无响应；Streamable HTTP 下服务器回 202/空体）。"""
        ...

    async def close(self) -> None: ...


def _parse_sse(text: str) -> list[tuple[str, str]]:
    """解析一段完整的 SSE 文本为 [(event, data)] 列表（MCP 响应的事件流）。

    SSE 规范：以空行分隔事件；data: 行累积为 data 字段；event: 行指定事件名；
    事件名缺省为 "message"。调用方应保证 text 是"以空行结尾的完整事件块"。
    """
    events: list[tuple[str, str]] = []
    event_name = "message"
    data_lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line == "":
            if data_lines:
                events.append((event_name, chr(10).join(data_lines)))
                data_lines = []
            event_name = "message"
            continue
        if line.startswith(":"):
            continue  # 注释行
        if line.startswith("event:"):
            event_name = line[len("event:") :].strip()
        elif line.startswith("data:"):
            data_lines.append(line[len("data:") :].strip())
    if data_lines:
        events.append((event_name, chr(10).join(data_lines)))
    return events


def _split_sse_events(text: str) -> tuple[list[tuple[str, str]], str]:
    """增量切分 SSE 流（M2-fix）：只消费以空行结尾的完整事件块，残余留给下一次。

    真实服务器走 chunked 传输时，事件会跨 chunk 拆分——若每个 chunk 都独立解析
    （旧实现 buffer 逐 chunk 清空），半截事件会被丢弃导致响应永远等不到。这里
    把未闭合（无空行结尾）的部分保留在 buffer，等后续 chunk 补全。
    空行分隔符兼容 \n\n 与 \r\n\r\n。

    返回 (完整事件列表, 残余文本)。
    """
    events: list[tuple[str, str]] = []
    remaining = text
    while True:
        idx = remaining.find("\n\n")
        sep = 2
        if idx == -1:
            idx = remaining.find("\r\n\r\n")
            sep = 4
            if idx == -1:
                break
        block = remaining[:idx]
        remaining = remaining[idx + sep :]
        events.extend(_parse_sse(block))
    return events, remaining


def _first_json(data: str) -> Any:
    """从可能含多行/多事件的 data 里取出第一条 JSON。"""
    for line in data.splitlines():
        line = line.strip()
        if line:
            return json.loads(line)
    raise McpProtocolError("SSE data 为空，无法解析 JSON-RPC 响应")


class StreamableHttpTransport:
    """Streamable HTTP 传输（MCP 2025 现代标准）。

    POST {url}，Accept 同时声明 application/json 与 text/event-stream：
      - 单响应：body 直接是 JSON-RPC 结果
      - 流式：body 是 SSE，取第一个 event 的 data
    连接复用 httpx.AsyncClient（长连接 + 连接池）。
    """

    def __init__(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self._url = url
        self._headers = dict(headers or {})
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._request_id = 0

    async def connect(self) -> None:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)

    async def request(self, method: str, params: dict[str, Any] | None) -> dict[str, Any]:
        await self.connect()
        assert self._client is not None
        self._request_id += 1
        payload = build_request(method, params, self._request_id)
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            **self._headers,
        }
        try:
            resp = await self._client.post(self._url, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            raise McpConnectionError(f"MCP 请求失败: {exc}") from exc
        if resp.status_code >= 400:
            raise McpConnectionError(f"MCP 服务器返回 HTTP {resp.status_code}: {resp.text[:200]}")
        ctype = resp.headers.get("content-type", "")
        if "text/event-stream" in ctype:
            events = _parse_sse(resp.text)
            if not events:
                raise McpProtocolError("MCP 流式响应为空（无任何 SSE 事件）")
            return parse_response(_first_json(events[-1][1]))
        try:
            return parse_response(resp.json())
        except (json.JSONDecodeError, ValueError) as exc:
            raise McpProtocolError(f"MCP 响应非 JSON: {resp.text[:200]!r}") from exc

    async def notify(self, method: str, params: dict[str, Any] | None) -> None:
        await self.connect()
        assert self._client is not None
        payload = build_notification(method, params)
        headers = {"Content-Type": "application/json", **self._headers}
        try:
            await self._client.post(self._url, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            raise McpConnectionError(f"MCP 通知发送失败: {exc}") from exc
        # 通知不期待内容；2xx 即视为送达（202 Accepted 或 200 空体均合法）

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None


class SseTransport:
    """HTTP+SSE 经典传输（2024-11-05 形态）。

    GET {url} 打开事件流：先收到 event: endpoint 事件（告知消息端点），
    之后的 event: message 携带 JSON-RPC 响应。POST 消息走发现的 endpoint。

    实现：后台任务读事件流，把带 id 的响应投进队列；request() 发 POST 后
    等匹配 id 的响应（带超时）。endpoint 发现前发的请求会等待连接就绪。
    """

    def __init__(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self._url = url
        self._headers = dict(headers or {})
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._endpoint: str | None = None
        self._request_id = 0
        self._ready = asyncio.Event()
        self._reader_task: asyncio.Task | None = None
        self._responses: dict[int, asyncio.Future] = {}

    async def connect(self) -> None:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(self._timeout, read=None))
        self._reader_task = asyncio.create_task(self._read_loop())

    async def _read_loop(self) -> None:
        assert self._client is not None
        try:
            async with self._client.stream("GET", self._url, headers=self._headers) as resp:
                if resp.status_code >= 400:
                    raise McpConnectionError(f"SSE 流 HTTP {resp.status_code}")
                buffer = ""
                async for chunk in resp.aiter_text():
                    buffer += chunk
                    # M2-fix：只消费以空行结尾的完整事件，半截事件保留在 buffer，
                    # 等后续 chunk 补全（真实 chunked 传输下事件必跨块拆分）
                    events, buffer = _split_sse_events(buffer)
                    for event, data in events:
                        self._handle_event(event, data)
        except Exception as exc:  # noqa: BLE001 - 后台任务异常显式化
            logger.warning("MCP SSE 读取器退出: %s", exc)
            for fut in self._responses.values():
                if not fut.done():
                    fut.set_exception(McpConnectionError(f"MCP SSE 流中断: {exc}"))

    def _handle_event(self, event: str, data: str) -> None:
        if event == "endpoint":
            # endpoint 可能是绝对 URL 或相对路径（如 /message），相对路径基于 base 解析
            self._endpoint = urljoin(self._url, data.strip())
            self._ready.set()
            return
        if event != "message":
            return
        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            logger.warning("MCP SSE 非法 JSON 事件: %s", data[:100])
            return
        rid = payload.get("id")
        fut = self._responses.pop(rid, None) if isinstance(rid, int) else None
        if fut is not None and not fut.done():
            fut.set_result(payload)

    async def request(self, method: str, params: dict[str, Any] | None) -> dict[str, Any]:
        assert self._client is not None
        await asyncio.wait_for(self._ready.wait(), timeout=self._timeout)
        endpoint = self._endpoint
        if endpoint is None:
            raise McpConnectionError("MCP SSE 未发现 endpoint 事件")
        self._request_id += 1
        rid = self._request_id
        payload = build_request(method, params, rid)
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self._responses[rid] = fut
        try:
            resp = await self._client.post(endpoint, json=payload, headers=self._headers)
            if resp.status_code >= 400:
                raise McpConnectionError(f"MCP 消息端点 HTTP {resp.status_code}")
            result = await asyncio.wait_for(fut, timeout=self._timeout)
        except TimeoutError as exc:
            self._responses.pop(rid, None)
            raise McpConnectionError(f"MCP 请求 {method} 超时") from exc
        finally:
            self._responses.pop(rid, None)
        return parse_response(result)

    async def notify(self, method: str, params: dict[str, Any] | None) -> None:
        assert self._client is not None
        await asyncio.wait_for(self._ready.wait(), timeout=self._timeout)
        endpoint = self._endpoint
        if endpoint is None:
            raise McpConnectionError("MCP SSE 未发现 endpoint 事件")
        await self._client.post(
            endpoint, json=build_notification(method, params), headers=self._headers
        )

    async def close(self) -> None:
        if self._reader_task is not None:
            self._reader_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reader_task
            self._reader_task = None
        if self._client is not None:
            await self._client.aclose()
            self._client = None


def build_transport(
    url: str,
    *,
    transport: str = "streamable_http",
    headers: dict[str, str] | None = None,
    timeout: float = _DEFAULT_TIMEOUT,
) -> McpTransport:
    """按配置构造传输层（streamable_http | sse；未知值 fail-fast）。

    M3-fix：透传 timeout（此前 McpClient._timeout 未到达传输层，硬编码默认）。
    """
    if transport == "streamable_http":
        return StreamableHttpTransport(url, headers=headers, timeout=timeout)
    if transport == "sse":
        return SseTransport(url, headers=headers, timeout=timeout)
    raise ValueError(f"未知 MCP 传输: {transport!r}（可选 streamable_http|sse）")


class McpClient:
    """面向一个 MCP Server 的客户端门面（FR-2.2）。"""

    def __init__(
        self,
        url: str,
        *,
        transport: McpTransport | None = None,
        transport_kind: str = "streamable_http",
        headers: dict[str, str] | None = None,
        client_name: str = CLIENT_NAME,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self._url = url
        self._transport = transport or build_transport(
            url, transport=transport_kind, headers=headers, timeout=timeout
        )
        self._client_name = client_name
        self._timeout = timeout
        self._connected = False
        self._tool_cache: list[dict[str, Any]] | None = None

    @property
    def connected(self) -> bool:
        return self._connected

    async def connect(self) -> dict[str, Any]:
        """握手：initialize -> notifications/initialized。返回服务器 capabilities。"""
        if self._connected:
            return {}
        await self._transport.connect()
        try:
            result = await self._transport.request(
                METHOD_INITIALIZE,
                {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": self._client_name, "version": "0.1.0"},
                },
            )
        except McpError as exc:
            await self._transport.close()
            raise McpConnectionError(f"MCP initialize 失败: {exc}") from exc
        await self._transport.notify(METHOD_INITIALIZED, {})
        self._connected = True
        return result

    async def list_tools(self, *, force: bool = False) -> list[dict[str, Any]]:
        """拉取服务器工具清单 [{name, description, inputSchema}]（带缓存）。"""
        if self._tool_cache is not None and not force:
            return self._tool_cache
        if not self._connected:
            await self.connect()
        result = await self._transport.request(METHOD_TOOLS_LIST, {})
        tools = result.get("tools", [])
        self._tool_cache = [t for t in tools if isinstance(t, dict)]
        return self._tool_cache

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> str:
        """调用工具，返回 text 内容；服务器 isError -> McpToolError（工具级失败）。"""
        if not self._connected:
            await self.connect()
        result = await self._transport.request(
            METHOD_TOOLS_CALL, {"name": name, "arguments": arguments or {}}
        )
        if result.get("isError"):
            raise McpToolError(extract_text_content(result) or f"MCP 工具 {name} 执行失败")
        return extract_text_content(result)

    async def close(self) -> None:
        self._connected = False
        self._tool_cache = None
        await self._transport.close()
