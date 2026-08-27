"""内置工具集（挂到 ToolRegistry）。"""

from __future__ import annotations

from tools_gateway.registry import Tool, ToolRegistry


def _echo(**kwargs: str) -> str:
    """原样返回输入文本（连通性/教学演示用）。"""
    return f"echo: {kwargs.get('text', '')}"


def create_default_registry() -> ToolRegistry:
    """创建含全部内置工具的注册表。"""
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
        )
    )
    return registry
