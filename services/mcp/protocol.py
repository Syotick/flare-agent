"""MCP 协议常量与 JSON-RPC 2.0 消息构造（零依赖，MCP 2025-06-18 规范）。

Model Context Protocol（MCP）本质是 JSON-RPC 2.0 over 可流式传输
（HTTP+SSE / Streamable HTTP）。本模块只负责"消息形状"：请求/响应/错误的结构化
+ 方法名常量 + 错误类型。不做任何网络 IO——传输层见 client.py。

真理：把协议层（形状）与传输层（字节）分离，才能做到传输可插拔
（开发用 Fake / 测试用真实 HTTP / 生产换官方 SDK 都不动协议层）。
"""

from __future__ import annotations

from typing import Any

# MCP 协议版本（2025-06-18 为 2025 年中稳定版）
PROTOCOL_VERSION = "2025-06-18"
CLIENT_NAME = "flare-agent"

# --- MCP 方法名常量 ---
METHOD_INITIALIZE = "initialize"
METHOD_INITIALIZED = "notifications/initialized"  # 通知：无响应
METHOD_TOOLS_LIST = "tools/list"
METHOD_TOOLS_CALL = "tools/call"

# --- JSON-RPC 错误码（标准码 + MCP 自定义码） ---
# 标准 JSON-RPC 错误码见 https://www.jsonrpc.org/specification#error_object
ERROR_PARSE_ERROR = -32700
ERROR_INVALID_REQUEST = -32600
ERROR_METHOD_NOT_FOUND = -32601
ERROR_INVALID_PARAMS = -32602
ERROR_INTERNAL_ERROR = -32603


class McpError(Exception):
    """MCP 层错误（协议/网络/服务器返回的 JSON-RPC error）。"""

    def __init__(self, message: str, *, code: int | None = None, data: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.data = data


class McpConnectionError(McpError):
    """连接/握手失败（服务器不可达、初始化失败）。"""


class McpProtocolError(McpError):
    """响应不合法（缺 result/error、id 不匹配、非法 JSON）。"""


class McpToolError(McpError):
    """服务器 tools/call 返回 isError（工具执行失败，但协议本身 OK）。"""


def build_request(method: str, params: dict[str, Any] | None, request_id: int) -> dict[str, Any]:
    """构造一个 JSON-RPC 2.0 请求。"""
    payload: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        payload["params"] = params
    return payload


def build_notification(method: str, params: dict[str, Any] | None) -> dict[str, Any]:
    """构造一个 JSON-RPC 2.0 通知（无 id，服务器不回响应）。"""
    payload: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        payload["params"] = params
    return payload


def parse_response(payload: Any) -> dict[str, Any]:
    """解析 JSON-RPC 响应：返回 result dict；失败抛 McpProtocolError / McpError。

    - payload 必须为 dict 且 jsonrpc == "2.0"
    - 有 result -> 返回之（非 dict 包一层 "_value"）
    - 有 error  -> 抛 McpError（带 code/message）
    - 其它     -> McpProtocolError
    """
    if not isinstance(payload, dict) or payload.get("jsonrpc") != "2.0":
        raise McpProtocolError(f"非法 JSON-RPC 响应: {str(payload)[:200]!r}")
    if "result" in payload:
        result = payload["result"]
        return result if isinstance(result, dict) else {"_value": result}
    error = payload.get("error")
    if isinstance(error, dict):
        raise McpError(
            str(error.get("message", "unknown rpc error")),
            code=error.get("code"),
            data=error.get("data"),
        )
    raise McpProtocolError(f"响应既无 result 也无 error: {str(payload)[:200]!r}")


def extract_text_content(result: dict[str, Any]) -> str:
    """从 tools/call 的 result.content 提取纯文本（FR-2.2 观察回灌）。

    MCP 内容块规范：content 是 [{type, text|...}]；这里只取 type=="text"，
    其余块（image/resource）记入说明，观察内容保持"文本可回灌"。
    """
    blocks = result.get("content")
    if not isinstance(blocks, list):
        return str(result)
    parts: list[str] = []
    skipped: list[str] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text":
            parts.append(str(block.get("text", "")))
        else:
            skipped.append(str(block.get("type", "?")))
    text = chr(10).join(p for p in parts if p)
    if skipped:
        text = text + (chr(10) if text else "") + f"(已忽略 MCP 内容块: {', '.join(skipped)})"
    return text
