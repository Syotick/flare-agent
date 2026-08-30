"""工具注册表：工具系统的最小核心（M2-4a）。

工具 = 名称 + 描述 + 参数 Schema(JSON Schema) + 执行函数(async)。
边界（防上帝模块）：注册/查询/执行只在此类；权限/限流/审计/审批做独立层（M3+）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

import jsonschema

from flare_common.errors import NotFoundError, ValidationError


@dataclass
class ToolResult:
    """工具执行结果（结构化，供 Agent 观察回传；A2）。"""

    ok: bool
    content: str = ""
    error_code: str | None = None
    artifacts: dict[str, Any] = field(default_factory=dict)  # 预留：文件/引用等


class ToolFunc(Protocol):
    async def __call__(self, **kwargs: Any) -> ToolResult: ...


# F2.4 工具权限分级：read（只读，安全）< write（可写，低风险）< destructive（破坏性，强制审批）
PERMISSION_READ = "read"
PERMISSION_WRITE = "write"
PERMISSION_DESTRUCTIVE = "destructive"
PERMISSION_ORDER: dict[str, int] = {
    PERMISSION_READ: 0,
    PERMISSION_WRITE: 1,
    PERMISSION_DESTRUCTIVE: 2,
}


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema（运行时校验 + 供 LLM 生成参数）
    func: ToolFunc
    permission: str = PERMISSION_READ  # F2.4：read | write | destructive（审批门数据来源）


class ToolRegistry:
    """进程内工具注册表（只做注册/查询/执行；横切能力独立分层）。"""

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

    def task_view(self, cwd: str | None = None) -> ToolRegistry:
        """任务视图：共享工具 + 附加绑定工作区 cwd 的工具（不修改共享注册表）。

        cwd 为真实目录时附加 read/write/edit/glob/grep/bash（读代码/写代码/跑命令），
        每任务独立 observed 状态。无 cwd（default 工作区/CLI）退回纯共享工具。
        """
        view = ToolRegistry()
        view._tools.update(self._tools)
        if cwd:
            from tools_gateway.workspace_tools import build_workspace_tools

            for tool in build_workspace_tools(cwd):
                view.register(tool)
        return view

    def list(self) -> list[Tool]:
        return sorted(self._tools.values(), key=lambda t: t.name)

    async def execute(self, name: str, args: dict[str, Any] | None = None) -> ToolResult:
        """执行工具：先按 JSON Schema 校验参数（非法抛 422），再执行。

        工具内部错误不向上抛，转为结构化失败结果，便于 Agent 观察后重试/换路。
        """
        tool = self.get(name)
        params = args or {}
        try:
            jsonschema.validate(instance=params, schema=tool.parameters)
        except jsonschema.ValidationError as exc:
            raise ValidationError(f"工具 {name} 参数不合法: {exc.message}") from exc
        try:
            return await tool.func(**params)
        except NotFoundError:
            raise
        except Exception as exc:  # noqa: BLE001 - 工具内部错误转结构化结果
            return ToolResult(ok=False, error_code="TOOL_EXECUTION_ERROR", content=str(exc))
