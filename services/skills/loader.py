"""技能包加载：SKILL.md（声明式，FR-3.1）→ Skill 对象。

技能包目录结构（对齐 Codex SKILL.md 心智，简化到可落地）：
  <name>/
    SKILL.md          # frontmatter(name/description/required_tools) + 指令正文
    resources/        # 可选资源（提示词模板/示例/片段），原样读出供上下文注入

Skill 是不可变值对象：加载后只读。改名/更新 = 重装（install 覆盖语义由调用方决定）。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from skills.frontmatter import parse_frontmatter

logger = logging.getLogger(__name__)

SKILL_FILE = "SKILL.md"
RESOURCES_DIR = "resources"


@dataclass(frozen=True)
class Skill:
    """一个声明式技能包。"""

    name: str
    description: str
    instructions: str
    resources: dict[str, str] = field(default_factory=dict)
    required_tools: list[str] = field(default_factory=list)
    source_dir: str = ""

    def summarize(self) -> str:
        """一行摘要（skill_list 工具展示用）。"""
        extra = f"（依赖工具: {', '.join(self.required_tools)}）" if self.required_tools else ""
        return f"{self.name}: {self.description}{extra}"


def _read_resources(root: Path) -> dict[str, str]:
    """递归读 resources/ 下所有文本文件，返回 {相对路径: 内容}（UTF-8）。"""
    resources: dict[str, str] = {}
    res_dir = root / RESOURCES_DIR
    if not res_dir.is_dir():
        return resources
    for path in sorted(res_dir.rglob("*")):
        if path.is_file():
            try:
                resources[path.relative_to(res_dir).as_posix()] = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                logger.warning("技能资源读取失败 %s: %s", path, exc)
    return resources


def load_skill_dir(skill_dir: str | Path) -> Skill:
    """从目录加载技能包：校验 SKILL.md + frontmatter（name/description 必填）。"""
    root = Path(skill_dir)
    skill_file = root / SKILL_FILE
    if not skill_file.is_file():
        raise ValueError(f"技能包缺少 {SKILL_FILE}: {root}")
    text = skill_file.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)
    name = meta.get("name")
    description = meta.get("description")
    if not isinstance(name, str) or not name:
        raise ValueError(f"技能 {root} 缺 frontmatter name（必填）")
    if not isinstance(description, str) or not description:
        raise ValueError(f"技能 {name} 缺 frontmatter description（必填）")
    required = meta.get("required_tools", [])
    if isinstance(required, str):
        required = [t.strip() for t in required.split(",") if t.strip()]
    if not isinstance(required, list):
        raise ValueError(f"技能 {name} 的 required_tools 必须是列表或逗号分隔字符串")
    return Skill(
        name=name,
        description=description,
        instructions=body,
        resources=_read_resources(root),
        required_tools=[str(t) for t in required],
        source_dir=str(root.resolve()),
    )
