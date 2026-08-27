"""kb_search 工具：把 RAG 检索暴露给 Agent（M3a-F5.1 溯源引用）。

Agent 在对话中问"知识库里有没有 X"时，会调用本工具拿到带来源的片段，
再基于观察给出带引用的回答（引用 = title + chunk 序号）。
"""

from __future__ import annotations

from rag.pipeline import KnowledgeBase
from tools_gateway.registry import Tool, ToolResult


def _fmt_hit(hit) -> str:
    return f"[{hit.title} #{hit.chunk_index} | score={hit.score:.3f}] {hit.text[:200]}"


def build_kb_search_tool(kb: KnowledgeBase) -> Tool:
    """构建 kb_search 工具（绑定指定知识库实例；Agent 注册表注入用）。"""

    async def _kb_search(query: str, k: int = 4) -> ToolResult:
        hits = await kb.search(query, k=k)
        if not hits:
            return ToolResult(ok=True, content="知识库中没有找到相关片段。")
        lines = [f"在知识库中找到 {len(hits)} 个相关片段："]
        lines.extend(_fmt_hit(h) for h in hits)
        return ToolResult(
            ok=True,
            content="\n".join(lines),
            artifacts={
                "hits": [
                    {
                        "doc_id": h.doc_id,
                        "title": h.title,
                        "chunk_index": h.chunk_index,
                        "score": round(h.score, 4),
                        "text": h.text,
                    }
                    for h in hits
                ]
            },
        )

    return Tool(
        name="kb_search",
        description=(
            "在团队知识库中检索与 query 相关的片段，结果带来源引用(title+片段号+分数)。"
            "适合回答产品文档、规范、FAQ 等知识类问题。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "检索查询（自然语言）"},
                "k": {"type": "integer", "description": "返回片段数（默认 4）"},
            },
            "required": ["query"],
        },
        func=_kb_search,
    )
