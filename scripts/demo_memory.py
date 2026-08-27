"""分层记忆 demo（M3b）：写长期事实 + 记向量笔记 -> 上下文注入 -> 工具召回。

运行（仓库根目录，conda env flare-agent）：
    PYTHONPATH=services python scripts/demo_memory.py
"""

from __future__ import annotations

import asyncio

from memory.mem_tools import build_memory_tools
from memory.memory import MemoryManager
from tools_gateway.builtin import create_default_registry


async def main() -> None:
    mem = MemoryManager()
    registry = create_default_registry()
    for tool in build_memory_tools(mem):
        registry.register(tool)
    try:
        # 1) 长期事实（key-value，跨会话）
        await mem.remember_fact("user_name", "用户叫小明，偏好简洁的回答")
        await mem.remember_fact("deploy_env", "生产环境是阿里云 ACK，告警阈值 70%")
        # 2) 向量笔记（语义召回）
        nid = await mem.remember_note("发布流程：灰度 10% 观察 15 分钟后全量")
        print(f"[笔记] {nid[:8]}… 已记入向量记忆")

        print()
        print("=== build_context(query=部署) 注入 Agent 的上下文块 ===")
        print(await mem.build_context(query="部署"))

        print()
        print("=== mem_recall(query=怎么发版) 工具召回 ===")
        result = await registry.execute("mem_recall", {"query": "怎么发版"})
        print(result.content)
    finally:
        await mem.close()


if __name__ == "__main__":
    asyncio.run(main())
