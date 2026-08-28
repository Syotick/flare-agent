"""多 Agent 编排工具（F1.4）：spawn_subagent / await_subagent / list_subagents / run_subagents。

父 Agent 通过这四个工具把大任务拆成子任务并行执行、再收集汇总：
- spawn_subagent(prompt)：派生子任务，立即返回 id（后台跑）
- await_subagent(id)：等待子任务完成并取回输出
- list_subagents()：查看所有子任务状态（可观测）
- run_subagents(prompts)：批量 spawn + 并行收集（gather）——"并行"的核心原语

失败不向上抛：工具执行失败转结构化 ToolResult（error_code），模型可重试/换路。
"""

from __future__ import annotations

from typing import Any

from subagent.runtime import SubagentRuntime
from tools_gateway.registry import Tool, ToolResult

MAX_PROMPTS = 16  # 单次 run_subagents 的 prompt 数上限（防一次扇出过多）


def _summarize(record: Any) -> str:
    head = f"{record.subagent_id} [{record.status}] steps={record.step_count}"
    prompt = str(record.prompt)[:60]
    if record.status == "completed":
        return f"- {head}: {prompt} -> {str(record.output)[:120]}"
    detail = record.error or record.output or "无输出"
    return f"- {head}: {prompt} -> ! {str(detail)[:120]}"


def build_subagent_tools(runtime: SubagentRuntime) -> list[Tool]:
    async def _spawn(**kwargs: Any) -> ToolResult:
        prompt = kwargs.get("prompt", "")
        try:
            record = runtime.spawn(
                prompt,
                max_steps=kwargs.get("max_steps"),
                timeout=kwargs.get("timeout"),
            )
        except ValueError as exc:
            return ToolResult(ok=False, error_code="SUBAGENT_SPAWN_ERROR", content=str(exc))
        return ToolResult(
            ok=True,
            content=(
                f"已派生子任务 {record.subagent_id}（后台运行），用 "
                f"await_subagent(subagent_id={record.subagent_id}) 收集结果"
            ),
        )

    async def _await(**kwargs: Any) -> ToolResult:
        sid = kwargs.get("subagent_id", "")
        try:
            await runtime.await_subagent(sid, timeout=kwargs.get("timeout"))
        except KeyError as exc:
            return ToolResult(ok=False, error_code="SUBAGENT_NOT_FOUND", content=str(exc))
        record = runtime.get(sid)
        if record.status != "completed":
            detail = record.error or record.output or "无输出"
            return ToolResult(
                ok=False,
                error_code="SUBAGENT_FAILED",
                content=f"[{record.status}] {detail}",
            )
        return ToolResult(ok=True, content=f"[completed] {record.output}")

    async def _list(**kwargs: Any) -> ToolResult:
        records = runtime.list()
        if not records:
            return ToolResult(ok=True, content="尚无子任务")
        return ToolResult(ok=True, content=chr(10).join(_summarize(r) for r in records))

    async def _run(**kwargs: Any) -> ToolResult:
        prompts = kwargs.get("prompts") or []
        if not prompts:
            return ToolResult(ok=False, error_code="INVALID_ARGS", content="prompts 不能为空")
        if len(prompts) > MAX_PROMPTS:
            return ToolResult(
                ok=False,
                error_code="INVALID_ARGS",
                content=f"prompts 数量超上限（{MAX_PROMPTS}）",
            )
        results = await runtime.run_subagents(
            [str(p) for p in prompts],
            max_steps=kwargs.get("max_steps"),
            timeout=kwargs.get("timeout"),
        )
        lines: list[str] = []
        for r in results:
            status = r["status"]
            body = r["output"] if status == "completed" else (r["error"] or r["output"])
            lines.append(f"=== subagent {r['subagent_id']} [{status}] ===")
            lines.append(str(body))
        return ToolResult(ok=True, content=chr(10).join(lines))

    return [
        Tool(
            name="spawn_subagent",
            description=(
                "派生子任务（独立 Agent 循环，后台并行运行），立即返回 subagent_id，"
                "之后用 await_subagent 收集结果。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "子任务的目标指令"},
                    "max_steps": {"type": "integer", "description": "子 Agent 步骤预算（默认 3）"},
                    "timeout": {"type": "number", "description": "超时秒数（默认 30）"},
                },
                "required": ["prompt"],
            },
            func=_spawn,
        ),
        Tool(
            name="await_subagent",
            description="等待指定子任务完成并返回其输出（超时则标记 timed_out）。",
            parameters={
                "type": "object",
                "properties": {
                    "subagent_id": {"type": "string"},
                    "timeout": {
                        "type": "number",
                        "description": "等待超时秒数（默认子任务自身的 timeout）",
                    },
                },
                "required": ["subagent_id"],
            },
            func=_await,
        ),
        Tool(
            name="list_subagents",
            description="列出所有子任务的状态与结果摘要（可观测）。",
            parameters={"type": "object", "properties": {}},
            func=_list,
        ),
        Tool(
            name="run_subagents",
            description=(
                "并行执行一批子任务并收集全部结果（核心并行原语：spawn 全部 + gather）。"
                "prompts 传子任务指令数组。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "prompts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "子任务指令列表（最多 16 个）",
                    },
                    "max_steps": {"type": "integer"},
                    "timeout": {"type": "number"},
                },
                "required": ["prompts"],
            },
            func=_run,
        ),
    ]
