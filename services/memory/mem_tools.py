"""记忆工具（M3b）：mem_set 写长期事实，mem_recall 语义召回（向量+事实）。

让 Agent 具备持久化记忆：记住用户偏好/项目约定，后续会话可直接召回。
"""

from __future__ import annotations

from memory.memory import MemoryManager
from tools_gateway.registry import Tool, ToolResult


def _fact_relevance(query: str, fact) -> float:
    """M2：事实与 query 的相关度——字面重合计分；无重合得 0，按最近时间兜底。"""
    hay = f"{fact.key} {fact.value}"
    q = query.strip()
    if not q:
        return 0.0
    if q in hay:
        return 3.0
    score = sum(1 for t in q.split() if t and t in hay)
    if score:
        return float(score)
    grams = {q[i : i + 2] for i in range(len(q) - 1)}  # 中文无空格：用 2-gram 计分
    return float(sum(1 for g in grams if g in hay)) * 0.5


def build_memory_tools(memory: MemoryManager) -> list[Tool]:
    """构建记忆工具集（mem_set / mem_recall），绑定指定 MemoryManager。"""

    async def _mem_set(key: str, value: str) -> ToolResult:
        fact = await memory.remember_fact(key, value)
        return ToolResult(ok=True, content=f"已记住 {key}={fact.value[:80]}")

    async def _mem_recall(query: str, k: int = 3) -> ToolResult:
        hits = await memory.search_memory(query, k=k)
        # M2：不再全量倾倒项目事实——按与 query 的相关度排序 + 封顶 k+2 条（F4.3：只给相关的）
        facts = await memory.list_facts()
        ordered = sorted(
            ((_fact_relevance(query, f), f) for f in facts),
            key=lambda pair: (-pair[0], -pair[1].updated_at),
        )
        facts = [f for _, f in ordered[: k + 2]]
        lines: list[str] = []
        if facts:
            lines.append("长期事实（相关）：")
            lines.extend(f"- {f.key}: {f.value[:150]}" for f in facts)
        if hits:
            lines.append("向量记忆命中：")
            lines.extend(f"- [{h.source}] {h.text[:150]} (score={h.score:.3f})" for h in hits)
        if not lines:
            return ToolResult(ok=True, content="记忆中没有相关内容。")
        return ToolResult(
            ok=True,
            content="\n".join(lines),
            artifacts={"facts": [f.key for f in facts], "hits": [h.text for h in hits]},
        )

    return [
        Tool(
            name="mem_set",
            description=(
                "把一条长期事实写入项目记忆（key 简短、value 一句话），"
                "例如偏好、约定、账号信息。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "事实的键（简短英文/中文）"},
                    "value": {"type": "string", "description": "事实内容"},
                },
                "required": ["key", "value"],
            },
            func=_mem_set,
        ),
        Tool(
            name="mem_recall",
            description=(
                "召回长期记忆：项目事实 + 与 query 语义相关的笔记。"
                "回答用户私有/历史信息前先查它。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "要回忆的内容描述"},
                    "k": {"type": "integer", "description": "向量召回条数（默认 3）"},
                },
                "required": ["query"],
            },
            func=_mem_recall,
        ),
    ]
