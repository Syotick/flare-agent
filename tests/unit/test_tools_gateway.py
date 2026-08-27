"""工具注册表测试。"""

from __future__ import annotations

import pytest

from flare_common.errors import NotFoundError, ValidationError
from tools_gateway.builtin import create_default_registry
from tools_gateway.registry import Tool, ToolRegistry, ToolResult


@pytest.fixture
def registry() -> ToolRegistry:
    return create_default_registry()


async def test_register_and_execute_echo(registry: ToolRegistry) -> None:
    result = await registry.execute("echo", {"text": "hello"})
    assert result.ok is True
    assert result.content == "echo: hello"


async def test_list_tools_sorted(registry: ToolRegistry) -> None:
    assert [t.name for t in registry.list()] == ["echo"]


async def test_unknown_tool_raises(registry: ToolRegistry) -> None:
    with pytest.raises(NotFoundError):
        await registry.execute("no_such_tool", {})


async def test_invalid_args_rejected(registry: ToolRegistry) -> None:
    # required 缺失 -> 校验层 422，绝不静默（A1/A2 契约）
    with pytest.raises(ValidationError):
        await registry.execute("echo", {})


async def test_duplicate_register_raises() -> None:
    reg = ToolRegistry()

    async def _tool(**kwargs: object) -> ToolResult:
        return ToolResult(ok=True, content="ok")

    tool = Tool(name="x", description="d", parameters={}, func=_tool)
    reg.register(tool)
    with pytest.raises(ValueError):
        reg.register(tool)


async def test_tool_internal_error_becomes_failed_result() -> None:
    reg = ToolRegistry()

    async def _boom(**kwargs: str) -> ToolResult:
        raise RuntimeError("boom")

    reg.register(
        Tool(
            name="boom",
            description="d",
            parameters={"type": "object", "properties": {}},
            func=_boom,
        )
    )
    result = await reg.execute("boom", {})
    assert result.ok is False
    assert result.error_code == "TOOL_EXECUTION_ERROR"
    assert "boom" in result.content
