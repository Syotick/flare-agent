"""沙箱工具（M4）：把沙箱执行器包成 Agent 可调用的 sandbox_run 工具。

工具失败不抛异常，转结构化 ToolResult（SANDBOX_TIMEOUT/SANDBOX_EXIT），
Agent 观察后重试/换路（与 registry 的失败观察契约一致）。
"""

from __future__ import annotations

from sandbox.runner import SandboxRunner, SandboxUnavailableError
from tools_gateway.registry import PERMISSION_DESTRUCTIVE, Tool, ToolResult


def build_sandbox_run_tool(sandbox: SandboxRunner) -> Tool:
    async def _run(code: str, language: str = "python", stdin: str | None = None) -> ToolResult:
        try:
            result = await sandbox.run(code, language=language, stdin=stdin)
        except SandboxUnavailableError as exc:
            return ToolResult(ok=False, error_code=exc.code, content=exc.message)
        if result.timed_out:
            return ToolResult(
                ok=False, error_code="SANDBOX_TIMEOUT", content="执行超时（进程已终止）"
            )
        parts: list[str] = []
        if result.stdout:
            parts.append("stdout:\n" + result.stdout)
        if result.stderr:
            parts.append("stderr:\n" + result.stderr)
        if not parts:
            parts.append("(无输出，退出码 0)")
        content = "\n\n".join(parts)
        if not result.ok:
            return ToolResult(
                ok=False,
                error_code="SANDBOX_EXIT",
                content=f"exit={result.exit_code} 耗时{result.duration_s}s\n{content}",
            )
        return ToolResult(
            ok=True,
            content=f"exit=0 耗时{result.duration_s}s\n{content}",
            artifacts={"exit_code": result.exit_code, "duration_s": result.duration_s},
        )

    return Tool(
        name="sandbox_run",
        description="在隔离沙箱执行 Python 代码，返回输出与退出码，可现场验证计算或跑脚本。",
        parameters={
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "要执行的 Python 代码"},
                "language": {
                    "type": "string",
                    "enum": ["python"],
                    "description": "语言（当前仅 python）",
                },
                "stdin": {"type": "string", "description": "可选标准输入"},
            },
            "required": ["code"],
        },
        func=_run,
        permission=PERMISSION_DESTRUCTIVE,  # F2.4：执行任意代码=破坏性，默认需人工审批
    )
