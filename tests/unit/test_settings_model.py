"""模型设置 API（控制台「模型」页）测试：持久化 / 脱敏 / env 优先 / 热生效 / 连通性测试。

安全断言重点：GET 绝不回传 api_key 明文；key 只在服务端文件里（0600）。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent_runtime.app import create_app
from agent_runtime.model_config import ModelConfigStore
from agent_runtime.routes.model import build_model_router
from agent_runtime.tasks import TaskManager
from flare_common.config import Settings
from flare_common.errors import ValidationError
from model_gateway.gateway import RetryProvider
from model_gateway.mock import MockModelProvider
from tools_gateway.builtin import create_default_registry


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        env="test",
        model_config_path=str(tmp_path / "model_config.json"),
    )


def _router_app(tmp_path: Path, tm: TaskManager | None = None):
    store = ModelConfigStore(_settings(tmp_path))
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse

    from flare_common.errors import FlareError

    app = FastAPI()
    app.include_router(build_model_router(store, tm))

    @app.exception_handler(FlareError)
    async def _on_flare_error(_request, exc: FlareError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code, content={"detail": {"message": exc.message}}
        )

    return app, store


def test_default_is_mock_and_sanitized(tmp_path: Path) -> None:
    store = ModelConfigStore(_settings(tmp_path))
    eff = store.effective()
    assert eff["provider"] == "mock" and eff["model_name"]
    desc = store.describe()
    assert desc["provider"] == "mock"
    assert desc["has_api_key"] is False and desc["api_key_source"] == "none"
    assert "api_key" not in desc  # 永不回传明文


def test_save_persists_and_masks_key(tmp_path: Path) -> None:
    store = ModelConfigStore(_settings(tmp_path))
    desc = store.save(
        {
            "provider": "openai",
            "base_url": "https://api.deepseek.com/v1",
            "model_name": "deepseek-chat",
            "api_key": "sk-secret-123",
        }
    )
    assert desc["provider"] == "openai"
    assert desc["has_api_key"] is True and desc["api_key_source"] == "file"
    assert "sk-secret-123" not in json.dumps(desc)  # 脱敏
    # 明文只在服务端文件里
    on_disk = json.loads((tmp_path / "model_config.json").read_text(encoding="utf-8"))
    assert on_disk["api_key"] == "sk-secret-123"
    # 再读 effective 也保留 key（服务端可用）
    assert store.effective()["api_key"] == "sk-secret-123"


def test_env_overrides_local_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = ModelConfigStore(_settings(tmp_path))
    store.save(
        {"provider": "openai", "base_url": "https://x/v1", "model_name": "m", "api_key": "k"}
    )
    # 真实环境变量压制本地 JSON（生产/CI 覆盖 UI 配置）
    monkeypatch.setenv("FLARE_MODEL_PROVIDER", "mock")
    eff = store.effective()
    assert eff["provider"] == "mock"
    assert eff["api_key"] == "k"  # env 未覆盖的字段仍用本地配置
    assert eff["api_key_source"] == "file"


def test_clear_api_key(tmp_path: Path) -> None:
    store = ModelConfigStore(_settings(tmp_path))
    store.save({"api_key": "sk-x"})
    assert store.describe()["has_api_key"] is True
    store.save({"api_key": ""})  # 空串 = 清除
    assert store.describe()["has_api_key"] is False
    assert "api_key" not in store._load()


def test_save_validation(tmp_path: Path) -> None:
    store = ModelConfigStore(_settings(tmp_path))
    with pytest.raises(ValidationError):
        store.save({"provider": "nope"})
    with pytest.raises(ValidationError):
        store.save({"provider": "openai", "base_url": "ftp://x", "model_name": "m"})
    with pytest.raises(ValidationError):
        store.save({"provider": "openai", "base_url": "https://x/v1", "model_name": ""})


def test_partial_update_keeps_others(tmp_path: Path) -> None:
    store = ModelConfigStore(_settings(tmp_path))
    store.save(
        {"provider": "openai", "base_url": "https://a/v1", "model_name": "m1", "api_key": "k1"}
    )
    store.save({"model_name": "m2"})  # 只改一个字段
    eff = store.effective()
    assert eff["model_name"] == "m2"
    assert eff["provider"] == "openai" and eff["base_url"] == "https://a/v1"
    assert eff["api_key"] == "k1"


def test_presets_list(tmp_path: Path) -> None:
    with TestClient(_router_app(tmp_path)[0]) as client:
        presets = client.get("/v1/settings/model/presets").json()
        ids = {p["id"] for p in presets}
        assert {"anthropic", "openai", "deepseek", "dashscope", "custom"}.issubset(ids)
        assert all(p["provider"] in ("openai", "anthropic") for p in presets)
        assert any(p["id"] == "anthropic" and p["provider"] == "anthropic" for p in presets)


def test_put_get_flow(tmp_path: Path) -> None:
    with TestClient(_router_app(tmp_path)[0]) as client:
        assert client.get("/v1/settings/model").json()["provider"] == "mock"
        resp = client.put(
            "/v1/settings/model",
            json={
                "provider": "openai",
                "base_url": "https://api.deepseek.com/v1",
                "model_name": "deepseek-chat",
                "api_key": "sk-put-1",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["provider"] == "openai" and body["has_api_key"] is True
        assert "sk-put-1" not in json.dumps(body)
        # 持久化后 GET 一致（脱敏）
        got = client.get("/v1/settings/model").json()
        assert got["model_name"] == "deepseek-chat" and got["api_key_source"] == "file"


def test_put_hot_reload_swaps_llm(tmp_path: Path) -> None:
    tm = TaskManager(registry=create_default_registry(), llm=MockModelProvider())
    assert isinstance(tm.llm, MockModelProvider)
    try:
        with TestClient(_router_app(tmp_path, tm)[0]) as client:
            resp = client.put(
                "/v1/settings/model",
                json={
                    "provider": "openai",
                    "base_url": "https://api.deepseek.com/v1",
                    "model_name": "deepseek-chat",
                    "api_key": "sk-hot",
                },
            )
            assert resp.status_code == 200
        # 热生效：模型网关已换成 openai 兼容（RetryProvider 包裹）
        assert isinstance(tm.llm, RetryProvider)
        assert tm.llm is not None
    finally:
        import asyncio

        asyncio.run(tm.close())


def test_test_endpoint_mock_and_openai_failure(tmp_path: Path) -> None:
    with TestClient(_router_app(tmp_path)[0]) as client:
        ok = client.post("/v1/settings/model/test", json={}).json()
        assert ok == {"ok": True, "mode": "mock", "models": ["flare-agent"]}
        # openai 协议 + 不可达端点 -> 明确失败信息（临时覆盖，不保存）
        bad = client.post(
            "/v1/settings/model/test",
            json={"provider": "openai", "base_url": "http://127.0.0.1:1/v1", "model_name": "m"},
        ).json()
        assert bad["ok"] is False and bad["mode"] == "openai" and bad["error"]


def test_mounted_in_create_app(tmp_path: Path) -> None:
    app = create_app(settings=_settings(tmp_path))
    with TestClient(app) as client:
        assert client.get("/v1/settings/model").status_code == 200
        assert client.get("/v1/settings/model/presets").status_code == 200
        assert client.get("/v1/settings/model").json()["provider"] == "mock"


def test_profiles_crud(tmp_path: Path) -> None:
    with TestClient(_router_app(tmp_path)[0]) as client:
        # 新建自定义供应商
        resp = client.post(
            "/v1/settings/model/profiles",
            json={
                "name": "某中转站",
                "provider": "openai",
                "base_url": "https://relay.example.com/v1",
                "model_name": "gpt-5.4",
                "api_key": "sk-relay-1",
            },
        )
        assert resp.status_code == 200
        prof = resp.json()
        assert prof["name"] == "某中转站"
        assert prof["provider"] == "openai"
        assert prof["has_api_key"] is True
        assert "api_key" not in prof  # 脱敏：不回明文
        pid = prof["id"]

        # 列表脱敏
        lst = client.get("/v1/settings/model/profiles").json()
        assert len(lst) == 1
        assert lst[0]["id"] == pid
        assert "api_key" not in lst[0]

        # 更新：改名 + 换协议 + 覆盖 key
        upd = client.put(
            f"/v1/settings/model/profiles/{pid}",
            json={
                "name": "中转站新名",
                "provider": "anthropic",
                "base_url": "https://relay.example.com",
                "model_name": "claude-sonnet-5",
                "api_key": "sk-relay-2",
            },
        ).json()
        assert upd["name"] == "中转站新名"
        assert upd["provider"] == "anthropic"
        assert upd["has_api_key"] is True

        # key 缺省/空串 = 保持已有 key
        upd2 = client.put(f"/v1/settings/model/profiles/{pid}", json={"name": "中转站新名2"}).json()
        assert upd2["name"] == "中转站新名2"
        assert upd2["has_api_key"] is True

        # 删除
        assert client.delete(f"/v1/settings/model/profiles/{pid}").status_code == 200
        assert client.get("/v1/settings/model/profiles").json() == []
        assert client.delete(f"/v1/settings/model/profiles/{pid}").status_code == 422


def test_profiles_validation(tmp_path: Path) -> None:
    with TestClient(_router_app(tmp_path)[0]) as client:
        assert (
            client.post(
                "/v1/settings/model/profiles", json={"name": "", "provider": "openai"}
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/v1/settings/model/profiles", json={"name": "x", "provider": "nope"}
            ).status_code
            == 422
        )
        # 真实模型缺 model_name
        assert (
            client.post(
                "/v1/settings/model/profiles",
                json={"name": "x", "provider": "openai", "base_url": "https://x/v1"},
            ).status_code
            == 422
        )
        assert (
            client.put("/v1/settings/model/profiles/no-such", json={"name": "x"}).status_code == 422
        )
