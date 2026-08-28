"""SKILL.md 的 frontmatter 解析（零依赖，YAML 子集）。

只支持"平面键值"元信息（skill 元信息就够用）：
  - 标量：字符串（可带引号）、整数、浮点、布尔
  - 列表：内联 [a, b] 或块级 - item
不支持嵌套映射（复杂结构用 JSON 字符串值）；解析失败抛 ValueError（fail-fast）。

真理：技能元信息是"声明式契约"——解析失败宁可报错也不静默当空，否则
一个坏 SKILL.md 会让模型得到错误的技能清单（静默错误比显式失败更危险）。
"""

from __future__ import annotations

import json
import re
from typing import Any


def _parse_scalar(raw: str) -> Any:
    """把一个字符串值解析为 Python 标量（int/float/bool/str）。"""
    value = raw.strip()
    if value == "":
        return ""
    if value.startswith('"') and value.endswith('"'):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value[1:-1]
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        items = _split_top_level(inner)
        return [_parse_scalar(i) for i in items]
    if value == "true":
        return True
    if value == "false":
        return False
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"-?\d+\.\d+", value):
        return float(value)
    return value


def _split_top_level(text: str) -> list[str]:
    """按逗号切分，跳过引号内逗号（内联列表用）。"""
    parts: list[str] = []
    current: list[str] = []
    in_quote: str | None = None
    for ch in text:
        if in_quote is not None:
            current.append(ch)
            if ch == in_quote:
                in_quote = None
            continue
        if ch in ("'", '"'):
            in_quote = ch
            current.append(ch)
        elif ch == ",":
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    parts.append("".join(current).strip())
    return [p for p in parts if p]


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """解析文档开头的 YAML frontmatter（--- 包裹）。

    返回 (meta, body)：meta 为键值 dict；body 为 frontmatter 之后的内容。
    没有 frontmatter -> ({}, text 原样)。只有开头的 --- 没有闭合 -> ValueError。
    """
    if not text.startswith("---"):
        return {}, text
    lines = text.splitlines()
    if len(lines) < 2:
        raise ValueError("frontmatter 未闭合: 缺少结束 ---")
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        raise ValueError("frontmatter 未闭合: 缺少结束 ---")
    meta: dict[str, Any] = {}
    for i in range(1, end):
        line = lines[i]
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- "):
            raise ValueError("块级列表当前仅支持作为键的重复项？请使用内联列表 [a, b] 或简化元信息")
        if ":" not in line:
            raise ValueError(f"frontmatter 行无法解析（缺冒号）: {line!r}")
        key, _, raw = line.partition(":")
        key = key.strip()
        if not key:
            raise ValueError(f"frontmatter 键为空: {line!r}")
        meta[key] = _parse_scalar(raw)
    body = chr(10).join(lines[end + 1 :]).strip() + chr(10)
    return meta, body
