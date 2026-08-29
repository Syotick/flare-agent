"""能力盘点 REST API（前端入口闭环）：把已交付但只有 Agent 内部工具的
MCP / Skills / 多 Agent / 工具注册表 暴露成只读 HTTP 接口，供控制台浏览。

背景：MCP/Skills/多 Agent 此前只以 agent 工具（mcp_list / skill_list / spawn_subagent…）
存在，Web 控制台没有入口 -> "死代码"（能力在，但产品层看不到）。本路由补上这块拼图。

端点：
- GET /v1/capabilities/tools              -> 工具注册表清单（name/description/JSON-Schema）
- GET /v1/capabilities/skills             -> 已安装技能清单
- GET /v1/capabilities/skills/{name}      -> 技能详情（指令 + 资源全文）
- GET /v1/capabilities/mcp                -> MCP 服务器状态快照（gateway.status()）
- GET /v1/capabilities/subagent           -> 多 Agent 运行时状态（活跃数 + 子任务记录）

只读、无副作用；可选依赖（skills/mcp/subagent 未装配时返回空），保证注入式测试可用。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from flare_common.errors import NotFoundError
from mcp.gateway import McpGateway
from skills.registry import SkillRegistry
from subagent.runtime import SubagentRuntime
from tools_gateway.registry import ToolRegistry


def build_capabilities_router(
    registry: ToolRegistry,
    *,
    skills: SkillRegistry | None = None,
    mcp_gateway: McpGateway | None = None,
    subagent_runtime: SubagentRuntime | None = None,
) -> APIRouter:
    """构建能力盘点路由（只读）。

    - registry: ToolRegistry（必填，工具清单数据源）
    - skills / mcp_gateway / subagent_runtime: 可选；未装配时对应端点返回空态，
      保证默认装配（完整）与注入式测试（部分）都能用。
    """
    router = APIRouter(prefix="/v1/capabilities", tags=["capabilities"])

    @router.get("/tools")
    async def list_tools() -> list[dict[str, Any]]:
        return [
            {"name": t.name, "description": t.description, "parameters": t.parameters}
            for t in registry.list()
        ]

    @router.get("/skills")
    async def list_skills() -> list[dict[str, Any]]:
        if skills is None:
            return []
        return [
            {
                "name": s.name,
                "description": s.description,
                "required_tools": s.required_tools,
                "resource_count": len(s.resources),
            }
            for s in skills.list()
        ]

    @router.get("/skills/{name}")
    async def get_skill(name: str) -> dict[str, Any]:
        if skills is None:
            raise HTTPException(
                status_code=404, detail={"code": "NOT_FOUND", "message": "技能库未装配"}
            )
        try:
            s = skills.get(name)
        except NotFoundError:
            raise HTTPException(
                status_code=404, detail={"code": "NOT_FOUND", "message": f"未知技能: {name}"}
            ) from None
        return {
            "name": s.name,
            "description": s.description,
            "instructions": s.instructions,
            "required_tools": s.required_tools,
            "resources": s.resources,
        }

    @router.get("/mcp")
    async def list_mcp() -> list[dict[str, Any]]:
        return mcp_gateway.status() if mcp_gateway is not None else []

    @router.get("/subagent")
    async def subagent_status() -> dict[str, Any]:
        if subagent_runtime is None:
            return {"active_count": 0, "records": []}
        records = [r.to_dict() for r in subagent_runtime.list()]
        active = sum(1 for r in records if r["status"] in ("pending", "running"))
        return {"active_count": active, "records": records}

    return router
