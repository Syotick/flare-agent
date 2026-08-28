"""Skills 机制测试（FR-3）：frontmatter 解析 / 技能加载 / 注册表 / 工具。"""

from __future__ import annotations

from pathlib import Path

import pytest

from flare_common.errors import NotFoundError
from skills.frontmatter import parse_frontmatter
from skills.loader import load_skill_dir
from skills.registry import SkillRegistry
from tools_gateway.registry import ToolRegistry


def write_skill(
    root: Path, name: str, description: str, body: str = "步骤一：xxx", required: str | None = None
) -> Path:
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    fm = f"---\nname: {name}\ndescription: {description}\n"
    if required is not None:
        fm += f"required_tools: {required}\n"
    fm += "---\n"
    (d / "SKILL.md").write_text(fm + body, encoding="utf-8")
    return d


def test_parse_frontmatter_scalars():
    text = (
        "---\nname: code-review\ndescription: 审查代码\n"
        "max_steps: 5\nverbose: true\ntags: [a, b]\n---\n正文\n"
    )
    meta, body = parse_frontmatter(text)
    assert meta["name"] == "code-review"
    assert meta["description"] == "审查代码"
    assert meta["max_steps"] == 5
    assert meta["verbose"] is True
    assert meta["tags"] == ["a", "b"]
    assert body.startswith("正文")


def test_parse_frontmatter_no_frontmatter():
    meta, body = parse_frontmatter("plain text")
    assert meta == {} and body == "plain text"


def test_parse_frontmatter_unclosed_raises():
    with pytest.raises(ValueError):
        parse_frontmatter("---\nname: x\n")


def test_parse_frontmatter_bad_line_raises():
    with pytest.raises(ValueError):
        parse_frontmatter("---\nno-colon-line\n---\n")


def test_load_skill_dir_with_resources(tmp_path: Path):
    d = write_skill(tmp_path, "code-review", "按规范审查代码")
    res = d / "resources"
    res.mkdir()
    (res / "checklist.md").write_text("- 检查错误处理", encoding="utf-8")
    skill = load_skill_dir(d)
    assert skill.name == "code-review"
    assert "步骤一" in skill.instructions
    assert skill.resources["checklist.md"] == "- 检查错误处理"


def test_load_skill_dir_missing_skillmd_raises(tmp_path: Path):
    with pytest.raises(ValueError):
        load_skill_dir(tmp_path)


def test_registry_install_list_uninstall(tmp_path: Path):
    src = write_skill(tmp_path, "code-review", "审查", required="[kb_search]")
    lib = tmp_path / "lib"
    reg = SkillRegistry(lib)
    skill = reg.install(src)
    assert skill.name == "code-review"
    assert skill.required_tools == ["kb_search"]
    names = [s.name for s in reg.list()]
    assert "code-review" in names
    # 重复安装不覆盖 -> 报错（显式）
    with pytest.raises(ValueError):
        reg.install(src)
    # overwrite 可覆盖
    reg.install(src, overwrite=True)
    reg.uninstall("code-review")
    assert reg.list() == []
    with pytest.raises(NotFoundError):
        reg.get("code-review")


def test_registry_build_context(tmp_path: Path):
    src1 = write_skill(tmp_path, "a", "技能A", "A 指令")
    src2 = write_skill(tmp_path, "b", "技能B", "B 指令")
    lib = tmp_path / "lib"
    reg = SkillRegistry(lib)
    reg.install(src1)
    reg.install(src2)
    ctx = reg.build_context(["a", "b"])
    assert "技能：a" in ctx and "A 指令" in ctx
    assert "技能：b" in ctx and "B 指令" in ctx


async def test_skill_tools_via_registry(tmp_path: Path):
    from skills.skill_tools import build_skill_tools

    src = write_skill(tmp_path, "code-review", "审查", "严格审查代码")
    lib = tmp_path / "lib"
    reg = SkillRegistry(lib)
    reg.install(src)
    registry = ToolRegistry()
    for tool in build_skill_tools(reg):
        registry.register(tool)
    listed = await registry.execute("skill_list", {})
    assert listed.ok is True and "code-review" in listed.content
    loaded = await registry.execute("skill_load", {"name": "code-review"})
    assert loaded.ok is True and "严格审查代码" in loaded.content
    # 未知技能 -> 结构化失败（不抛异常）
    missing = await registry.execute("skill_load", {"name": "nope"})
    assert missing.ok is False and missing.error_code == "SKILL_NOT_FOUND"
