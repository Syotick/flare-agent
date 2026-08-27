"""词法分析（M3c）：中英混合 tokenize，供 BM25 关键词检索与覆盖度重排共用。

- ASCII 词：小写字母/数字/下划线整体为一个词元；
- 中文：提取 CJK 字符序列后按 2-gram 切（与 HashEmbedder 的 n-gram 对齐，保证一致性）。
"""

from __future__ import annotations

import re

_CJK_RE = re.compile(r"[^\u4e00-\u9fff]")
_ASCII_RE = re.compile(r"[a-z0-9_]+")


def tokenize(text: str) -> list[str]:
    """把文本切成词元列表（ASCII 词 + 中文 2-gram）。"""
    text = text.lower()
    tokens: list[str] = []
    for word in _ASCII_RE.findall(text):
        tokens.append(word)
    cjk = _CJK_RE.sub("", text)
    if len(cjk) >= 2:
        tokens.extend(cjk[i : i + 2] for i in range(len(cjk) - 1))
    elif cjk:
        tokens.append(cjk)
    return tokens
