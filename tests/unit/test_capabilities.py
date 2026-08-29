"""能力盘点 API 测试（前端入口闭环配套）。

覆盖：/v1/capabilities/{tools,skills,skills/{name},mcp,subagent} 只读契约、
未知技能 404、create_app 默认装配下挂载可用（真实数据走同一注册表）。
"""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent_runtime.app import create_app
from agent_runtime.routes.capabilities import build_capabilities_router
from flare_common.config import Settings
from mcp.gateway import McpGateway, McpServerConfig
from model_gateway.mock import MockModelProvider
from skills.registry import SkillRegistry
from subagent.runtime import SubagentRuntime
from tools_gateway.builtin import create_default_registry
from tools_gateway.registry import Tool, ToolResult


def _dummy_tool(name: str, description: str) -> Tool:
    async def func(text: str = "x") -> ToolResult:
        return ToolResult(ok=True, content=f"{name}:{text}")

    return Tool(
        name=name,
        description=description,
        parameters={"type": "object", "properties": {"text": {"type": "string"}}},
        func=func,
    )


def _mini_app(registry, **kw) -> FastAPI:
    app = FastAPI()
    app.include_router(build_capabilities_router(registry, **kw))
    return app


def _skill_dir() -> str:
    tmp = tempfile.mkdtemp(prefix="flare-skill-")
    (Path(tmp) / "code-review").mkdir(parents=True)
    frontmatter = (
        "---\nname: code-review\ndescription: 代码审查技能\nrequired_tools: [sandbox_run]\n---\n"
    )
    (Path(tmp) / "code-review" / "SKILL.md").write_text(
        frontmatter + "审查代码时先定位变更再逐项检查。",
        encoding="utf-8",
    )
    return tmp


def test_tools_endpoint_lists_registry() -> None:
    reg = create_default_registry()
    with TestClient(_mini_app(reg)) as client:
        tools = client.get("/v1/capabilities/tools").json()
    assert tools and any(t["name"] == "echo" for t in tools)
    echo = next(t for t in tools if t["name"] == "echo")
    assert echo["description"] and echo["parameters"]["type"] == "object"


def test_skills_endpoint_lists_and_detail() -> None:
    skills = SkillRegistry(_skill_dir())
    reg = create_default_registry()
    with TestClient(_mini_app(reg, skills=skills)) as client:
        lst = client.get("/v1/capabilities/skills").json()
        assert lst and lst[0]["name"] == "code-review"
        assert lst[0]["required_tools"] == ["sandbox_run"]
        detail = client.get("/v1/capabilities/skills/code-review").json()
        assert "审查代码" in detail["instructions"]
        assert detail["name"] == "code-review"
        assert client.get("/v1/capabilities/skills/nope").status_code == 404


def test_skills_empty_when_not_configured() -> None:
    with TestClient(_mini_app(create_default_registry())) as client:
        assert client.get("/v1/capabilities/skills").json() == []


def test_mcp_endpoint_returns_status_snapshot() -> None:
    gw = McpGateway(
        [
            McpServerConfig(
                name="echo", url="http://localhost:9001/mcp", transport="streamable_http"
            ),
            McpServerConfig(name="db", url="http://localhost:9002/mcp", enabled=False),
        ]
    )
    with TestClient(_mini_app(create_default_registry(), mcp_gateway=gw)) as client:
        status = client.get("/v1/capabilities/mcp").json()
    assert len(status) == 2
    by_name = {s["name"]: s for s in status}
    assert by_name["echo"]["connected"] is False
    assert by_name["echo"]["transport"] == "streamable_http"
    assert by_name["db"]["enabled"] is False


async def test_subagent_endpoint_lists_records() -> None:
    import asyncio

    runtime = SubagentRuntime(MockModelProvider(), create_default_registry())
    rec = runtime.spawn("hello")
    deadline = time.time() + 5
    while not rec.done and time.time() < deadline:
        await asyncio.sleep(0.02)
    with TestClient(_mini_app(create_default_registry(), subagent_runtime=runtime)) as client:
        body = client.get("/v1/capabilities/subagent").json()
    assert body["active_count"] == 0
    assert len(body["records"]) == 1
    assert body["records"][0]["subagent_id"] == rec.subagent_id
    assert "echo: hello" in body["records"][0]["output"]


def test_capabilities_mounted_in_create_app() -> None:
    """默认装配：工具清单非空 + 子 Agent 状态可用（与 /v1/tasks 同进程同一注册表）。"""
    app = create_app(settings=Settings(env="test"))
    with TestClient(app) as client:
        tools = client.get("/v1/capabilities/tools").json()
        sub = client.get("/v1/capabilities/subagent").json()
        mcp = client.get("/v1/capabilities/mcp").json()
        skills = client.get("/v1/capabilities/skills").json()
    assert len(tools) >= 5  # echo + kb_search + mem 工具 + mcp/skill/subagent 工具
    names = {t["name"] for t in tools}
    assert {
        "echo",
        "kb_search",
        "spawn_subagent",
        "run_subagents",
        "skill_list",
        "mcp_list",
    } <= names
    assert sub["active_count"] == 0
    assert mcp == []  # 默认 FLARE_MCP_SERVERS=[] 未配置服务器
    assert isinstance(skills, list)
