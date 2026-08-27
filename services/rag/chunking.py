"""文档切块（M3a-F5.1）。

策略：固定窗口 + 重叠；优先在段落边界切（避免把语义拦腰截断），
单个超长段落按字符窗口硬切 + overlap（不丢内容）。
"""

from __future__ import annotations

DEFAULT_CHUNK_SIZE = 600
DEFAULT_OVERLAP = 80


def split_text(
    text: str, *, chunk_size: int = DEFAULT_CHUNK_SIZE, overlap: int = DEFAULT_OVERLAP
) -> list[str]:
    """把 text 切成若干 chunk（字符粒度）。

    - 空输入返回 []；
    - 段落(非空行)贪心合并进当前 chunk，直到放不下再开新块；
    - 单个段落超长时按窗口硬切，块间保留 overlap 字符。
    """
    if not text:
        return []
    if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("chunk_size 需 > 0，且 0 <= overlap < chunk_size")

    paragraphs = [p.strip() for p in text.splitlines() if p.strip()]
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        if len(para) > chunk_size:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(_hard_split(para, chunk_size, overlap))
            continue
        if current and len(current) + 1 + len(para) > chunk_size:
            chunks.append(current)
            current = para
        else:
            current = (current + "\n" + para).strip() if current else para
    if current:
        chunks.append(current)
    return chunks


def _hard_split(text: str, chunk_size: int, overlap: int) -> list[str]:
    step = max(1, chunk_size - overlap)
    out: list[str] = []
    i = 0
    while i < len(text):
        out.append(text[i : i + chunk_size])
        i += step
        if i >= len(text):
            break
    return out
