"""工具注册表：工具系统的最小核心（M2-4a）。

工具 = 名称 + 描述(供 LLM 选择) + 参数 Schema(JSON Schema) + 执行函数。
后续演进：MCP 适配、权限分级、鉴权、审计（见 02-module-design.md §3）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from flare_common.errors import NotFoundError


class ToolFunc(Protocol):
    def __call__(self, **kwargs: Any) -> str: ...


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema（供 LLM 生成参数）
    func: ToolFunc


class ToolRegistry:
    """进程内工具注册表（后续可加权限/审计）。"""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"工具已存在: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        tool = self._tools.get(name)
        if tool is None:
            raise NotFoundError(f"未知工具: {name}")
        return tool

    def list(self) -> list[Tool]:
        return sorted(self._tools.values(), key=lambda t: t.name)

    def execute(self, name: str, args: dict[str, Any] | None = None) -> str:
        tool = self.get(name)
        return tool.func(**(args or {}))
