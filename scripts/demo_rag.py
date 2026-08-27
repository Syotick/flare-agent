"""RAG 知识库 demo（M3a）：入库三份文档 -> 检索 -> 展示带来源的结果。

运行（在仓库根目录，conda env flare-agent）：
    PYTHONPATH=services python scripts/demo_rag.py
"""

from __future__ import annotations

import asyncio

from rag.pipeline import KnowledgeBase

DOCS = [
    (
        "部署指南",
        "所有服务统一部署到阿里云 ACK 集群。生产环境必须配置负载均衡 SLB 与水平扩缩容，"
        "容量告警阈值 70%，超过后自动扩容并通知值班群。测试环境使用命名空间 test。",
    ),
    (
        "发布规范",
        "发布流程：1) 构建镜像并推送 ACR；2) 灰度 10% 观察 15 分钟；"
        "3) 全量发布；4) 回滚用上一版本镜像。每周四 22:00 固定发布窗口，禁止周五下午发版。",
    ),
    (
        "FAQ",
        "如何重置本地缓存？删除 data/cache 目录后重启服务即可。如何查看任务日志？"
        "在控制台任务详情页点开步骤卡片，或 GET /v1/tasks/{id}/stream。",
    ),
]


async def main() -> None:
    kb = KnowledgeBase()
    try:
        for title, content in DOCS:
            r = await kb.ingest(title=title, content=content)
            print(f"[入库] {title}: {r.chunk_count} 块 / {r.chars} 字符")
        print()
        for q in ["怎么在阿里云上发布", "如何重置本地缓存", "和知识库无关的提问"]:
            print(f"[查询] {q}")
            hits = await kb.search(q, k=2)
            if not hits:
                print("  (无命中)")
            for h in hits:
                print(f"  · [{h.title} #{h.chunk_index} | score={h.score:.3f}] {h.text[:70]}…")
            print()
    finally:
        await kb.close()


if __name__ == "__main__":
    asyncio.run(main())
