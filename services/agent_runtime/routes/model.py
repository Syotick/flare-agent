"""模型设置 REST API（控制台「模型」视图的数据源）。

背景：此前模型配置只走环境变量（FLARE_MODEL_*），改 key/供应商要改 .env 后重启。
本路由补上可视化配置闭环：
- GET  /v1/settings/model           -> 当前生效配置（脱敏：key 只回 has_api_key/来源）
- PUT  /v1/settings/model           -> 保存（部分更新；api_key 空串=清除），保存后热生效
- GET  /v1/settings/model/presets   -> 常用供应商模板（前端下拉一键填充）
- POST /v1/settings/model/test      -> 连通性测试（body 可带临时覆盖，不保存）

安全：api_key 明文只在服务端（data/model_config.json，0600），API 永不回传；
生产用 env/K8s Secret 覆盖本地配置（真实环境变量优先级最高）。
"""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter
from pydantic import BaseModel

from agent_runtime.model_config import MODEL_PRESETS, ModelConfigStore
from flare_common.errors import ValidationError
from model_gateway.gateway import build_provider

_PROVIDERS = ("mock", "openai")


class ModelConfigIn(BaseModel):
    """PUT 载荷：字段均可选（部分更新）；api_key 空串 = 清除已存 key。"""

    provider: str | None = None
    base_url: str | None = None
    model_name: str | None = None
    api_key: str | None = None


class ModelTestIn(BaseModel):
    """POST test 载荷：临时覆盖（不保存）。"""

    provider: str | None = None
    base_url: str | None = None
    model_name: str | None = None
    api_key: str | None = None


async def _test_connection(store: ModelConfigStore, payload: ModelTestIn | None) -> dict[str, Any]:
    """连通性测试：mock 直接 ok；openai 协议 GET {base}/models 验证端点/鉴权。"""
    eff = store.effective()
    if payload is not None:
        over = payload.model_dump(exclude_none=True)
        for key, val in over.items():
            if val != "":
                eff[key] = val
    if eff["provider"] not in _PROVIDERS:
        raise ValidationError(f"未知 model_provider: {eff['provider']!r}（可选 mock|openai）")
    if eff["provider"] == "mock":
        return {"ok": True, "mode": "mock", "models": ["flare-agent"]}

    base = eff["base_url"].rstrip("/")
    headers = {"Authorization": f"Bearer {eff['api_key']}"} if eff["api_key"] else {}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(base + "/models", headers=headers)
    except Exception as exc:  # noqa: BLE001 - 网络/超时错误要原样回显给用户
        return {"ok": False, "mode": "openai", "error": f"{type(exc).__name__}: {exc}"}
    if resp.status_code >= 400:
        body = (resp.text or "")[:200]
        return {"ok": False, "mode": "openai", "error": f"HTTP {resp.status_code}: {body}"}
    try:
        models = [m.get("id") for m in (resp.json().get("data") or []) if m.get("id")]
    except Exception:  # noqa: BLE001
        models = []
    return {"ok": True, "mode": "openai", "models": models[:50]}


def build_model_router(
    store: ModelConfigStore,
    task_manager: Any | None = None,
) -> APIRouter:
    """构建模型设置路由。

    - store: ModelConfigStore（必填，配置数据源）
    - task_manager: 可选；提供时保存配置后调用 set_llm 热替换模型网关（新建任务生效）
    """
    router = APIRouter(prefix="/v1/settings/model", tags=["model"])

    @router.get("")
    async def get_model_config() -> dict[str, Any]:
        return store.describe()

    @router.get("/presets")
    async def list_presets() -> list[dict[str, Any]]:
        return MODEL_PRESETS

    @router.put("")
    async def put_model_config(payload: ModelConfigIn) -> dict[str, Any]:
        if payload.provider is not None and payload.provider not in _PROVIDERS:
            raise ValidationError(
                f"未知 model_provider: {payload.provider!r}（可选 {'|'.join(_PROVIDERS)}）"
            )
        desc = store.save(payload.model_dump(exclude_none=True))
        if task_manager is not None:
            old = task_manager.set_llm(build_provider(store.to_settings()))
            close = getattr(old, "close", None)
            if close is not None:
                await close()
        return desc

    @router.post("/test")
    async def test_connection(payload: ModelTestIn | None = None) -> dict[str, Any]:
        return await _test_connection(store, payload)

    return router
