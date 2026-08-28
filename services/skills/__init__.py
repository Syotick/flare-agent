"""Skills 机制（FR-3）：声明式技能包。

- frontmatter.py：SKILL.md 元信息解析（零依赖 YAML 子集）
- loader.py：技能包目录 -> Skill 值对象（指令 + 资源 + 依赖工具）
- registry.py：SkillRegistry（安装/卸载/列表/上下文注入）
- skill_tools.py：skill_list / skill_load 工具

技能 = 声明式上下文资产：安装拷贝进技能库，激活 = 指令注入 Agent 上下文
（可执行部分继续走 ToolRegistry）。OSS 存储/签名校验随 FR-3.2 扩展。
"""

from skills.registry import SkillRegistry
from skills.skill_tools import build_skill_tools

__all__ = ["SkillRegistry", "build_skill_tools"]
