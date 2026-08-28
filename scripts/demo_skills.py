"""Skills demo（FR-3）：安装示例技能 -> 列表 -> 加载指令 -> 上下文注入。

运行（仓库根目录，conda env flare-agent）：
    PYTHONPATH=services python scripts/demo_skills.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from skills.registry import SkillRegistry
from skills.skill_tools import build_skill_tools
from tools_gateway.builtin import create_default_registry

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "examples" / "skills" / "code-review"


async def main() -> None:
    reg = SkillRegistry(ROOT / "data" / "skills")
    if not [s for s in reg.list() if s.name == "code-review"]:
        skill = reg.install(SAMPLE)
        print(f"[安装] {skill.name} -> {skill.source_dir}")

    registry = create_default_registry()
    for tool in build_skill_tools(reg):
        registry.register(tool)

    print("\n=== skill_list ===")
    print((await registry.execute("skill_list", {})).content)

    print("\n=== skill_load(code-review) 前 40 行 ===")
    content = (await registry.execute("skill_load", {"name": "code-review"})).content
    for line in content.splitlines()[:40]:
        print(line)

    print("\n=== 上下文注入（build_context）前 8 行 ===")
    ctx = reg.build_context(["code-review"])
    for line in ctx.splitlines()[:8]:
        print(line)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
