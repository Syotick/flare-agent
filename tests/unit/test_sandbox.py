"""沙箱测试（M4）：本地子进程执行/超时/输出上限/错误 + sandbox_run 工具 + Agent 集成。"""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from agent_runtime.app import create_app
from agent_runtime.graph import build_react_agent
from agent_runtime.tasks import TaskManager
from flare_common.config import Settings
from flare_common.errors import ValidationError
from model_gateway.providers import LLMResponse, ToolCall, ToolCallDecision
from sandbox import (
    DockerSandbox,
    LocalProcessSandbox,
    SandboxConfig,
    SandboxUnavailableError,
    build_sandbox,
)
from tools_gateway.builtin import create_default_registry


async def test_local_sandbox_run_ok() -> None:
    sb = LocalProcessSandbox()
    res = await sb.run("print('hello', 1 + 1)")
    assert res.ok
    assert res.exit_code == 0
    assert "hello 2" in res.stdout


async def test_local_sandbox_timeout_kills_process() -> None:
    sb = LocalProcessSandbox(SandboxConfig(timeout_s=1.0))
    res = await sb.run("import time; time.sleep(30)")
    assert res.timed_out
    assert not res.ok


async def test_local_sandbox_caps_output() -> None:
    sb = LocalProcessSandbox(SandboxConfig(max_output_chars=200))
    res = await sb.run("print('x' * 5000)")
    assert res.stdout.count("x") == 200  # 截断到上限
    assert "截断" in res.stdout


async def test_local_sandbox_reports_error() -> None:
    sb = LocalProcessSandbox()
    res = await sb.run("raise ValueError('boom')")
    assert not res.ok
    assert res.exit_code != 0
    assert "boom" in res.stderr


async def test_sandbox_run_tool_via_registry() -> None:
    reg = create_default_registry(sandbox=LocalProcessSandbox())
    assert "sandbox_run" in [t.name for t in reg.list()]
    r = await reg.execute("sandbox_run", {"code": "print(6 * 7)"})
    assert r.ok
    assert "42" in r.content
    r2 = await reg.execute("sandbox_run", {"code": "1 / 0"})
    assert not r2.ok
    assert r2.error_code == "SANDBOX_EXIT"
    with pytest.raises(ValidationError):
        await reg.execute("sandbox_run", {})  # 缺 code


class ScriptedSandboxProvider:
    """决策脚本：先 call_tool sandbox_run，观察后再 final（模拟真实模型原生工具调用）。"""

    model = "scripted"

    async def chat(self, messages, *, tools=None, **kw) -> LLMResponse:
        if messages[-1].role == "tool":
            return LLMResponse(
                content=ToolCallDecision(
                    action="final", answer="代码运行成功: " + messages[-1].content
                ).model_dump_json(),
                model="scripted",
            )
        return LLMResponse(
            content=ToolCallDecision(
                action="call_tool",
                tool=ToolCall(name="sandbox_run", args={"code": "print('PASS')"}),
            ).model_dump_json(),
            model="scripted",
        )

    async def stream(self, messages, **kw):
        resp = await self.chat(messages, **kw)
        yield resp.content


async def test_agent_runs_code_via_sandbox() -> None:
    reg = create_default_registry(sandbox=LocalProcessSandbox())
    agent = build_react_agent(ScriptedSandboxProvider(), reg, max_steps=3)
    final = await agent.ainvoke({"task_input": "跑一段代码"})
    assert final["status"] == "completed"
    assert final["step_count"] == 1  # 一次工具执行
    assert "PASS" in final["output"]


async def test_agent_receives_native_tools_param() -> None:
    # L6：上游(OpenCode Zen)对 stream+tools 会断连，actor 走 stream（不带 tools）；
    # stream 异常时降级一次性 chat 并携带 tools（function-calling schema）。
    # 本测试模拟"上游流式不可用"→ 验证降级 chat 正确传递 tools。
    captured: dict = {}

    class CaptureProvider:
        async def chat(self, messages, *, tools=None, **kw):
            captured["tools"] = tools
            return LLMResponse(
                content=ToolCallDecision(action="final", answer="done").model_dump_json(), model="c"
            )

        async def stream(self, messages, **kw):
            raise RuntimeError("upstream stream unsupported")  # 模拟上游 stream+tools 断连

    reg = create_default_registry(sandbox=LocalProcessSandbox())
    agent = build_react_agent(CaptureProvider(), reg, max_steps=2)
    await agent.ainvoke({"task_input": "x"})
    names = [t["function"]["name"] for t in captured["tools"]]
    assert "sandbox_run" in names
    assert "echo" in names


async def test_docker_sandbox_fail_fast() -> None:
    with pytest.raises(SandboxUnavailableError):
        await DockerSandbox().run("print(1)")


def test_build_sandbox_by_env() -> None:
    assert isinstance(build_sandbox(Settings(env="dev")), LocalProcessSandbox)
    assert isinstance(build_sandbox(Settings(env="prod")), DockerSandbox)


def test_task_api_with_sandbox_agent() -> None:
    tm = TaskManager(
        registry=create_default_registry(sandbox=LocalProcessSandbox()),
        llm=ScriptedSandboxProvider(),
    )
    with TestClient(create_app(task_manager=tm)) as client:
        r = client.post("/v1/tasks", json={"task_input": "运行代码计算 40+2"})
        assert r.status_code == 202
        task_id = r.json()["task_id"]
        detail: dict = {}
        for _ in range(100):
            detail = client.get(f"/v1/tasks/{task_id}").json()
            if detail["status"] in ("completed", "failed", "budget_exceeded"):
                break
            time.sleep(0.05)
        assert detail["status"] == "completed", detail
        assert "PASS" in detail["result"]["output"]
