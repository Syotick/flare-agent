"""冒烟测试：配置加载 + Agent Runtime 应用工厂 + 错误契约。"""

from __future__ import annotations

from importlib.metadata import version

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from agent_runtime.app import create_app
from flare_common.config import Settings
from flare_common.errors import NotFoundError


def test_settings_defaults() -> None:
    s = Settings(_env_file=None)
    assert s.app_name == "flare-agent"
    assert s.env == "dev"
    assert s.model_provider == "mock"


def test_settings_from_env() -> None:
    s = Settings(_env_file=None, env="test", model_provider="deepseek")
    assert s.env == "test"
    assert s.model_provider == "deepseek"


def test_settings_reject_unknown_env() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, unknown_field="x")


def test_health_with_injected_settings() -> None:
    app = create_app(Settings(_env_file=None, env="test"))
    with TestClient(app) as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "env": "test"}


def test_version() -> None:
    app = create_app()
    with TestClient(app) as client:
        resp = client.get("/version")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "flare-agent"
    # R3: /version 必须与 pyproject 同源，杜绝漂移
    assert body["version"] == version("flare-agent")


def test_flare_error_response_shape() -> None:
    app = create_app()

    @app.get("/_raise")
    async def raise_not_found() -> None:
        raise NotFoundError("no such thing")

    with TestClient(app) as client:
        resp = client.get("/_raise")
    assert resp.status_code == 404
    body = resp.json()
    assert body["code"] == "NOT_FOUND"
    assert body["message"] == "no such thing"
    assert "request_id" in body
