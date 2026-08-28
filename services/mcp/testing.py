"""MCP 测试/开发辅助：FakeTransport（进程内）+ MemoryMcpServer（真实 HTTP，stdlib）。

MemoryMcpServer 是最小但真实（走 HTTP + JSON-RPC）的 MCP Server：
  - POST {url}           -> Streamable HTTP 风格（单响应 JSON）
  - GET  {url}/sse       -> SSE 流（event: endpoint + event: message）
  - POST {url}/message   -> SSE 模式的消息端点（响应经 SSE 流回传）

用途：单元测试（FakeTransport）+ 集成测试（真实 HTTP 链路）+ 本地开发连一个
内置 echo/add 服务器验证 mcp_connect 工具。零外部依赖（仅 stdlib）。
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from mcp.protocol import (
    PROTOCOL_VERSION,
    McpConnectionError,
    McpError,
    McpProtocolError,
)

DEFAULT_TOOLS: list[dict[str, Any]] = [
    {
        "name": "echo",
        "description": "把 text 原样返回（连通性演示）。",
        "inputSchema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
    {
        "name": "add",
        "description": "计算 a + b（整数）。",
        "inputSchema": {
            "type": "object",
            "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
            "required": ["a", "b"],
        },
    },
]


def default_handlers() -> dict[str, Callable[[dict[str, Any]], str]]:
    return {
        "echo": lambda a: f"echo: {a['text']}",
        "add": lambda a: str(int(a["a"]) + int(a["b"])),
    }


class FakeTransport:
    """进程内传输：直接处理 JSON-RPC（无网络、确定性），单元测试用。

    与 MockModelProvider 同理——测试不依赖外部网络，但走的是真实协议形状。
    """

    def __init__(
        self,
        tools: list[dict[str, Any]] | None = None,
        handlers: dict[str, Callable[[dict[str, Any]], str]] | None = None,
        *,
        fail_initialize: bool = False,
    ) -> None:
        self.tools = list(tools) if tools is not None else list(DEFAULT_TOOLS)
        self.handlers = dict(handlers) if handlers is not None else default_handlers()
        self.fail_initialize = fail_initialize
        self.request_count = 0
        self.notified: list[str] = []
        self.closed = False

    async def connect(self) -> None:
        return None

    async def request(self, method: str, params: dict[str, Any] | None) -> dict[str, Any]:
        self.request_count += 1
        if method == "initialize":
            if self.fail_initialize:
                raise McpConnectionError("fake: initialize 失败（模拟不可达）")
            return {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "fake", "version": "0.1"},
            }
        if method == "tools/list":
            return {"tools": self.tools}
        if method == "tools/call":
            name = (params or {}).get("name")
            args = (params or {}).get("arguments", {})
            handler = self.handlers.get(name)
            if handler is None:
                raise McpError(f"unknown tool: {name}", code=-32601)
            return {"content": [{"type": "text", "text": handler(args)}]}
        raise McpProtocolError(f"unexpected method: {method}")

    async def notify(self, method: str, params: dict[str, Any] | None) -> None:
        self.notified.append(method)

    async def close(self) -> None:
        self.closed = True


class _SharedSseBuffer:
    """跨线程共享的 SSE 输出缓冲：POST 处理线程投递响应，GET 线程写出。"""

    def __init__(self) -> None:
        self._cv = threading.Condition()
        self._lines: list[str] = []

    def append(self, line: str) -> None:
        with self._cv:
            self._lines.append(line)
            self._cv.notify_all()

    def drain(self, timeout: float = 30.0) -> str | None:
        with self._cv:
            deadline = time.monotonic() + timeout
            while not self._lines:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                self._cv.wait(remaining)
            return self._lines.pop(0)


class _McpHttpServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        server_address,
        handler,
        *,
        tools: list[dict[str, Any]],
        handlers: dict[str, Callable[[dict[str, Any]], str]],
        sse_buffer: _SharedSseBuffer,
    ) -> None:
        super().__init__(server_address, handler)
        self.tools = tools
        self.handlers = handlers
        self.sse_buffer = sse_buffer


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args: Any) -> None:  # 静默访问日志
        return

    # --- 请求处理 ---

    def _rpc(self, payload: Any) -> dict[str, Any] | None:
        server: _McpHttpServer = self.server
        if not isinstance(payload, dict):
            return {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "parse error"},
            }
        method = payload.get("method")
        rid = payload.get("id")
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": rid,
                "result": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "memory-mcp", "version": "0.1"},
                },
            }
        if method == "notifications/initialized":
            return None  # 通知无响应
        if method == "tools/list":
            return {"jsonrpc": "2.0", "id": rid, "result": {"tools": server.tools}}
        if method == "tools/call":
            name = (payload.get("params") or {}).get("name")
            args = (payload.get("params") or {}).get("arguments", {})
            handler = server.handlers.get(name)
            if handler is None:
                return {
                    "jsonrpc": "2.0",
                    "id": rid,
                    "error": {"code": -32601, "message": f"unknown tool: {name}"},
                }
            return {
                "jsonrpc": "2.0",
                "id": rid,
                "result": {"content": [{"type": "text", "text": handler(args)}]},
            }
        return {
            "jsonrpc": "2.0",
            "id": rid,
            "error": {"code": -32601, "message": f"method not found: {method}"},
        }

    def do_GET(self) -> None:
        server: _McpHttpServer = self.server
        if self.path == "/sse":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(b"event: endpoint" + b"\n" + b"data: /message" + b"\n\n")
            self.wfile.flush()
            while True:
                line = server.sse_buffer.drain(timeout=30.0)
                if line is None:
                    break
                self.wfile.write(line.encode())
                self.wfile.flush()
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self) -> None:
        server: _McpHttpServer = self.server
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {}
        response = self._rpc(payload)
        if self.path == "/message":
            # SSE 模式：响应经 SSE 流回传，POST 只回 202
            if response is not None:
                server.sse_buffer.append(f"data: {json.dumps(response)}\n\n")
            self.send_response(202)
            self.end_headers()
            return
        data = json.dumps(response).encode() if response is not None else b""
        self.send_response(200 if response is not None else 202)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class MemoryMcpServer:
    """最小真实 MCP Server（stdlib http.server，零依赖）。

    >>> server = MemoryMcpServer.with_defaults().start()
    >>> client = McpClient(server.url)  # Streamable HTTP
    >>> await client.connect(); await client.list_tools()
    """

    def __init__(
        self,
        tools: list[dict[str, Any]] | None = None,
        handlers: dict[str, Callable[[dict[str, Any]], str]] | None = None,
    ) -> None:
        self.tools = list(tools) if tools is not None else list(DEFAULT_TOOLS)
        self.handlers = dict(handlers) if handlers is not None else default_handlers()
        self._httpd: _McpHttpServer | None = None
        self._thread: threading.Thread | None = None
        self.url = ""
        self.sse_url = ""

    @classmethod
    def with_defaults(cls) -> MemoryMcpServer:
        return cls()

    def start(self) -> MemoryMcpServer:
        sse = _SharedSseBuffer()
        self._httpd = _McpHttpServer(
            ("127.0.0.1", 0),
            _Handler,
            tools=self.tools,
            handlers=self.handlers,
            sse_buffer=sse,
        )
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        host, port = self._httpd.server_address[:2]
        self.url = f"http://{host}:{port}/mcp"
        self.sse_url = f"http://{host}:{port}/sse"
        return self

    def stop(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None
