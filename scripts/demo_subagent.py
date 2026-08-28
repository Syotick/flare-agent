"""多 Agent / Subagent 并行 demo（F1.4）：拆解大任务 -> 并行子任务 -> 汇总。

运行（仓库根目录，conda env flare-agent）：
    PYTHONPATH=services python scripts/demo_subagent.py
"""

from __future__ import annotations

import asyncio

from model_gateway.mock import MockModelProvider
from subagent.runtime import SubagentRuntime
from subagent.sub_tools import build_subagent_tools
from tools_gateway.builtin import create_default_registry


async def main() -> None:
    registry = create_default_registry()
    rt = SubagentRuntime(MockModelProvider(), registry, timeout=10.0)
    for tool in build_subagent_tools(rt):
        registry.register(tool)
    try:
        print("=== 场景：把『写周报』拆成 3 个并行子任务 ===")
        res = await registry.execute(
            "run_subagents",
            {"prompts": ["总结本周进展", "列出下周计划", "标注风险项"]},
        )
        print(res.content)

        print("\n=== list_subagents（可观测） ===")
        print((await registry.execute("list_subagents", {})).content)
    finally:
        await rt.close()


if __name__ == "__main__":
    asyncio.run(main())

