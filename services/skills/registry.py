"""技能注册表（FR-3.1）：技能包的发现/安装/卸载/上下文注入。

技能 = 声明式提示词资产，不是可执行代码：安装只是把目录拷进技能库，
真正"激活"是把它的指令（+ 资源 + 依赖工具清单）注入 Agent 上下文。
可执行部分（工具）继续走 ToolRegistry——两者分工清晰。

OSS 存储/签名校验/版本化（FR-3.2）随对象存储落地后扩展；本地先文件系统。
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from flare_common.errors import NotFoundError
from skills.loader import SKILL_FILE, Skill, load_skill_dir

logger = logging.getLogger(__name__)


class SkillRegistry:
    """文件系统技能库（skills_dir/<name>/SKILL.md）。"""

    def __init__(self, skills_dir: str | Path = "data/skills") -> None:
        self._dir = Path(skills_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        return self._dir

    def list(self) -> list[Skill]:
        """列出全部已安装技能（按名称排序）；损坏的技能包跳过并告警。"""
        skills: list[Skill] = []
        for child in sorted(self._dir.iterdir()):
            if not child.is_dir() or not (child / SKILL_FILE).is_file():
                continue
            try:
                skills.append(load_skill_dir(child))
            except ValueError as exc:
                logger.warning("技能包损坏，跳过 %s: %s", child.name, exc)
        return skills

    def get(self, name: str) -> Skill:
        for skill in self.list():
            if skill.name == name:
                return skill
        raise NotFoundError(f"未知技能: {name}")

    def install(self, source_dir: str | Path, *, overwrite: bool = False) -> Skill:
        """安装技能包（拷贝进技能库）。已存在且 overwrite=False 时抛错（显式）。"""
        src = Path(source_dir)
        skill = load_skill_dir(src)  # 先校验，失败不落盘（fail-fast）
        dest = self._dir / skill.name
        if dest.exists():
            if not overwrite:
                raise ValueError(f"技能已安装: {skill.name}（用 overwrite=True 覆盖）")
            shutil.rmtree(dest)
        shutil.copytree(src, dest)
        return load_skill_dir(dest)

    def uninstall(self, name: str) -> None:
        dest = self._dir / name
        if not dest.is_dir():
            raise NotFoundError(f"未知技能: {name}")
        shutil.rmtree(dest)

    def build_context(self, names: list[str]) -> str:
        """把若干技能的指令拼成上下文块（F4.3 上下文工程：给 Agent 的指令资产）。

        每个技能一段：### 技能 <name> + 说明 + 指令正文 + 依赖工具提示 + 可选资源。
        """
        blocks: list[str] = []
        for name in names:
            skill = self.get(name)
            lines = [f"### 技能：{skill.name}", f"说明：{skill.description}"]
            lines.append(skill.instructions.strip())
            if skill.required_tools:
                lines.append(
                    f"本技能依赖工具：{', '.join(skill.required_tools)}（可通过工具注册表调用）"
                )
            if skill.resources:
                lines.append("技能资源：")
                for rel, content in skill.resources.items():
                    lines.append(f"--- {rel} ---")
                    lines.append(content.strip())
            blocks.append(chr(10).join(lines))
        return chr(10).join(blocks)
