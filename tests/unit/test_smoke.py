"""冒烟测试：配置加载 + Agent Runtime 系统端点。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from agent_runtime.main import app
from common.config import Settings


def test_settings_defaults() -> None:
    s = Settings(_env_file=None)
    assert s.app_name == "flare-agent"
    assert s.env == "dev"
    assert s.model_provider == "mock"


def test_settings_from_env() -> None:
    s = Settings(_env_file=None, env="test", model_provider="deepseek")
    assert s.env == "test"
    assert s.model_provider == "deepseek"


def test_health() -> None:
    with TestClient(app) as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"


def test_version() -> None:
    with TestClient(app) as client:
        resp = client.get("/version")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "flare-agent"
    assert body["version"] == "0.1.0"
