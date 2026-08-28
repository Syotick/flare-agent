"""多 Agent / Subagent 并行（F1.4）。

- runtime.py：SubagentRuntime（子任务 = 独立 ReAct 循环，asyncio 并行 + 预算/超时/并发护栏）
- sub_tools.py：spawn_subagent / await_subagent / list_subagents / run_subagents 工具

父 Agent 把大任务拆成子任务并行执行、收集结果自行汇总（对齐 DSH/Codex 心智）。
"""

from subagent.runtime import SubagentRecord, SubagentRuntime
from subagent.sub_tools import build_subagent_tools

__all__ = ["SubagentRuntime", "SubagentRecord", "build_subagent_tools"]
