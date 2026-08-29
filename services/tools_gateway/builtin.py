"""内置工具集（挂到 ToolRegistry）。"""

from __future__ import annotations

from sandbox.sandbox_tools import build_sandbox_run_tool
from tools_gateway.registry import PERMISSION_READ, Tool, ToolRegistry, ToolResult


async def _echo(**kwargs: str) -> ToolResult:
    """原样返回输入文本（连通性/教学演示用）。"""
    return ToolResult(ok=True, content=f"echo: {kwargs['text']}")


def create_default_registry(sandbox=None) -> ToolRegistry:
    """创建含全部内置工具的注册表。

    sandbox：可选 SandboxRunner，传入则注册 sandbox_run 工具（M4，Agent 可执行代码）。
    """
    registry = ToolRegistry()
    registry.register(
        Tool(
            name="echo",
            description="把 text 参数原样返回，用于验证工具链路。",
            parameters={
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
            func=_echo,
            permission=PERMISSION_READ,  # F2.4：只读，无副作用
        )
    )
    if sandbox is not None:
        registry.register(build_sandbox_run_tool(sandbox))
    return registry
