"""M4 演示：沙箱三层用法（直接执行 -> 工具 -> Agent 决策调用）。

运行：PYTHONPATH=services python scripts/demo_sandbox.py
"""

import asyncio

from agent_runtime.graph import build_react_agent
from model_gateway.providers import LLMMessage, LLMResponse, ToolCall, ToolCallDecision
from sandbox import LocalProcessSandbox
from tools_gateway.builtin import create_default_registry


class ScriptedAgentProvider:
    """模拟真实模型：先调 sandbox_run 算答案，观察后给结论。"""

    model = "scripted"

    async def chat(self, messages, *, tools=None, **kw):
        if messages[-1].role == "tool":
            return LLMResponse(
                content=ToolCallDecision(
                    action="final", answer="计算结果：40+2=42（已由沙箱验证）"
                ).model_dump_json(),
                model=self.model,
            )
        return LLMResponse(
            content=ToolCallDecision(
                action="call_tool",
                tool=ToolCall(name="sandbox_run", args={"code": "print(40 + 2)"}),
            ).model_dump_json(),
            model=self.model,
        )


async def main():
    sb = LocalProcessSandbox()
    print("== 1) 直接执行 ==")
    r = await sb.run("print('2 ** 10 =', 2 ** 10)")
    print("  ok:", r.ok, "| stdout:", r.stdout.strip())

    print("== 2) 通过 sandbox_run 工具 ==")
    reg = create_default_registry(sandbox=sb)
    tool_res = await reg.execute("sandbox_run", {"code": "print(sum(range(101)))"})
    print("  ok:", tool_res.ok, "| content:", tool_res.content.replace(chr(10), " ")[:90])

    print("== 3) Agent 自主决策调用 ==")
    agent = build_react_agent(ScriptedAgentProvider(), reg, max_steps=3)
    final = await agent.ainvoke({"task_input": "帮我算 40 + 2 等于多少"})
    print("  status:", final["status"], "| output:", final["output"])


if __name__ == "__main__":
    asyncio.run(main())
