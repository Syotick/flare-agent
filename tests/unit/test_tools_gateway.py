"""工具注册表测试。"""

from __future__ import annotations

import pytest

from common.errors import NotFoundError
from tools_gateway.builtin import create_default_registry


def test_register_and_execute_echo() -> None:
    reg = create_default_registry()
    out = reg.execute("echo", {"text": "hello"})
    assert out == "echo: hello"


def test_list_tools_sorted() -> None:
    reg = create_default_registry()
    names = [t.name for t in reg.list()]
    assert names == ["echo"]


def test_unknown_tool_raises() -> None:
    reg = create_default_registry()
    with pytest.raises(NotFoundError):
        reg.execute("no_such_tool", {})


def test_duplicate_register_raises() -> None:
    from tools_gateway.registry import Tool, ToolRegistry

    reg = ToolRegistry()
    tool = Tool(name="x", description="d", parameters={}, func=lambda: "1")
    reg.register(tool)
    with pytest.raises(ValueError):
        reg.register(tool)
