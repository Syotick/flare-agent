"""技能内置工具（FR-3.1）：skill_list / skill_load，挂进 ToolRegistry。

- skill_list：列出已安装技能（名称+说明），让 Agent 知道有哪些技能可用。
- skill_load：加载指定技能的指令（+资源）到返回内容，Agent 将其纳入后续上下文。

真理：技能是"上下文资产"而非"可执行黑盒"——模型需要先看到指令才能照着做，
所以 skill_load 返回的是可回灌的文本（与工具观察同构），而不是执行副作用。
"""

from __future__ import annotations

from typing import Any

from flare_common.errors import NotFoundError
from skills.registry import SkillRegistry
from tools_gateway.registry import Tool, ToolResult


def build_skill_list_tool(registry: SkillRegistry) -> Tool:
    async def _list(**kwargs: Any) -> ToolResult:
        skills = registry.list()
        if not skills:
            return ToolResult(ok=True, content="技能库为空（FLARE_SKILLS_DIR 下无已安装技能）")
        return ToolResult(ok=True, content=chr(10).join(s.summarize() for s in skills))

    return Tool(
        name="skill_list",
        description="列出已安装的技能（名称+说明+依赖工具）。",
        parameters={"type": "object", "properties": {}},
        func=_list,
    )


def build_skill_load_tool(registry: SkillRegistry) -> Tool:
    async def _load(**kwargs: str) -> ToolResult:
        name = kwargs["name"]
        try:
            skill = registry.get(name)
        except NotFoundError as exc:
            return ToolResult(ok=False, error_code="SKILL_NOT_FOUND", content=str(exc))
        parts = [f"# 技能：{skill.name}", f"说明：{skill.description}"]
        parts.append(skill.instructions.strip())
        if skill.required_tools:
            parts.append("依赖工具：" + ", ".join(skill.required_tools))
        if skill.resources:
            parts.append("资源：")
            for rel, content in skill.resources.items():
                parts.append("```" + rel + "```")
                parts.append(content.strip())
        return ToolResult(ok=True, content=chr(10).join(parts))

    return Tool(
        name="skill_load",
        description="加载指定技能的完整指令（含资源）到上下文。name 用 skill_list 查询。",
        parameters={
            "type": "object",
            "properties": {"name": {"type": "string", "description": "技能名"}},
            "required": ["name"],
        },
        func=_load,
    )


def build_skill_tools(registry: SkillRegistry) -> list[Tool]:
    """技能工具集（skill_list + skill_load）。"""
    return [build_skill_list_tool(registry), build_skill_load_tool(registry)]
