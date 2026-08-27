"""上下文工程（M3b-F4.3）：截断、摘要压缩、预算分配。

开发版摘要用确定性截断（句子边界切），生产可换 LLM 摘要（model_gateway）。
assemble() 把「短期对话 + 长期事实 + 向量记忆」按预算拼成一块可注入 Agent 的上下文。
"""

from __future__ import annotations

_SENTENCE_END = "。！？!?.;；"


def estimate_chars(text: str) -> int:
    """字符级预算估算（token 更准，但字符数足够本地预算控制）。"""
    return len(text)


def summarize(text: str, max_chars: int = 160) -> str:
    """摘要压缩：超长文本在句子边界截断 + 省略号（生产换 LLM 摘要）。"""
    if len(text) <= max_chars:
        return text
    cut = text[: max_chars - 1]
    # 从后往前找最近句子边界，避免拦腰截断
    for i in range(len(cut) - 1, 0, -1):
        if cut[i] in _SENTENCE_END:
            return cut[: i + 1] + "…"
    return cut + "…"


def truncate(text: str, max_chars: int = 200) -> str:
    """硬截断（用于短期对话行）。"""
    return text if len(text) <= max_chars else text[: max_chars - 1] + "…"


def assemble(
    *,
    recent: list[str] | None = None,
    facts: list[tuple[str, str]] | None = None,
    hits: list[tuple[str, str, float]] | None = None,
    budget_chars: int = 1200,
) -> str:
    """拼装注入 Agent 的上下文块（F4.3）。

    - facts: [(key, value)] 项目长期记忆
    - hits: [(source, text, score)] 向量记忆召回
    - recent: 近期对话消息（仅取最近若干条）
    预算不足时优先保「事实 > 向量 > 对话」。
    """
    parts: list[str] = []
    if facts:
        lines = [f"- {k}: {summarize(v, 160)}" for k, v in facts]
        parts.append("[项目记忆]" + chr(10) + chr(10).join(lines))
    if hits:
        lines = [f"- [{src}] {summarize(t, 160)} (score={s:.2f})" for src, t, s in hits]
        parts.append("[向量记忆]" + chr(10) + chr(10).join(lines))
    if recent:
        lines = [truncate(m, 200) for m in recent[-4:]]
        parts.append("[近期对话]" + chr(10) + chr(10).join(lines))

    if not parts:
        return ""
    sep = chr(10) + chr(10)
    block = sep.join(parts)
    if len(block) <= budget_chars:
        return block
    # 超预算：先丢近期对话，再硬截断
    if recent and len(block) > budget_chars:
        block = sep.join(parts[:-1])
    return truncate(block, budget_chars)
