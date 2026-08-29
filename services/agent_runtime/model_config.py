"""模型配置存储（控制台「模型设置」页的后端）。

设计原则（企业级）：
- API Key 是敏感物：**只存服务端**（本地 data/model_config.json，仅本用户可读），
  GET 接口绝不回传明文，只回 has_api_key / api_key_source；
- 生效优先级：**真实环境变量 > 本地 JSON > pydantic(含 .env)** —— 生产用
  env/K8s Secret 覆盖即可压制 UI 保存的本地配置，UI 只是本地开发/自托管便利；
- 保存后热生效：PUT 经 task_manager.set_llm 重建模型网关，新建任务即用新配置
  （正在运行的任务不受影响）。
"""

from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path
from typing import Any

from flare_common.config import Settings
from flare_common.errors import ValidationError

# 模型供应商预设（前端一键填充 base_url + 模型候选；OpenAI 兼容 / Anthropic 原生协议）
MODEL_PRESETS: list[dict[str, Any]] = [
    {
        "id": "anthropic",
        "name": "Anthropic (Claude)",
        "provider": "anthropic",
        "base_url": "https://api.anthropic.com",
        "models": ["claude-sonnet-4-5", "claude-opus-4-1", "claude-haiku-4-5"],
    },
    {
        "id": "openai",
        "name": "OpenAI",
        "provider": "openai",
        "base_url": "https://api.openai.com/v1",
        "models": ["gpt-4o-mini", "gpt-4o", "gpt-4.1"],
    },
    {
        "id": "deepseek",
        "name": "DeepSeek",
        "provider": "openai",
        "base_url": "https://api.deepseek.com/v1",
        "models": ["deepseek-chat", "deepseek-reasoner"],
    },
    {
        "id": "dashscope",
        "name": "通义千问（阿里云百炼）",
        "provider": "openai",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "models": ["qwen-plus", "qwen-max", "qwen-turbo"],
    },
    {
        "id": "siliconflow",
        "name": "硅基流动",
        "provider": "openai",
        "base_url": "https://api.siliconflow.cn/v1",
        "models": [
            "deepseek-ai/DeepSeek-V3",
            "deepseek-ai/DeepSeek-R1",
            "Qwen/Qwen2.5-7B-Instruct",
        ],
    },
    {
        "id": "ollama",
        "name": "Ollama（本地）",
        "provider": "openai",
        "base_url": "http://localhost:11434/v1",
        "models": ["llama3.1", "qwen2.5"],
    },
    {
        "id": "vllm",
        "name": "vLLM（本地）",
        "provider": "openai",
        "base_url": "http://localhost:8000/v1",
        "models": ["Qwen2.5-7B-Instruct"],
    },
    {
        "id": "custom",
        "name": "自定义（OpenAI 兼容）",
        "provider": "openai",
        "base_url": "",
        "models": [],
    },
]

_FIELDS = ("provider", "base_url", "model_name", "api_key")
# 本地字段名 -> Settings 属性名（Settings 用 model_* 前缀）
_SETTINGS_ATTR = {
    "provider": "model_provider",
    "base_url": "model_base_url",
    "model_name": "model_name",
    "api_key": "model_api_key",
}
_VALID_PROVIDERS = ("mock", "openai", "anthropic")


class ModelConfigStore:
    """模型配置持久化（本地 JSON + env 优先覆盖）。

    - effective(): 合并当前生效配置（真实 env > 本地 JSON > pydantic/.env）
    - describe(): 脱敏视图（GET 用，永不回传明文 key）
    - save():     部分更新并落盘（api_key 空串=清除），返回脱敏视图
    - to_settings(): 把生效配置转成 Settings 快照（供 build_provider 装配）
    """

    def __init__(self, settings: Settings, path: str | None = None) -> None:
        self._settings = settings
        # path 缺省时跟随 Settings（FLARE_MODEL_CONFIG_PATH），保证测试注入的 tmp 路径生效
        self._path = Path(path) if path else Path(settings.model_config_path)

    # ---------- 读取 ----------

    def _env_value(self, field: str) -> str | None:
        """真实环境变量的值（不含 .env——那是 pydantic 解析层，属于 settings）。

        环境变量名跟随 Settings 字段：FLARE_MODEL_PROVIDER / FLARE_MODEL_API_KEY 等。
        """
        raw = os.environ.get(f"FLARE_{_SETTINGS_ATTR[field].upper()}")
        return raw.strip() if raw else None

    def _load(self) -> dict[str, str]:
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            return {k: str(v) for k, v in raw.items() if k in _FIELDS and v not in (None, "")}
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            # 缺失或损坏都按空配置处理，绝不阻断启动
            return {}

    def effective(self) -> dict[str, str]:
        """合并后的生效配置：真实环境变量 > 本地 JSON > settings(.env)。"""
        file_cfg = self._load()
        eff: dict[str, str] = {}
        for field in _FIELDS:
            env = self._env_value(field)
            if env is not None:
                eff[field] = env
            elif field in file_cfg:
                eff[field] = file_cfg[field]
            else:
                eff[field] = getattr(self._settings, _SETTINGS_ATTR[field])
        if eff["api_key"]:
            eff["api_key_source"] = "env" if self._env_value("api_key") else "file"
        else:
            eff["api_key_source"] = "none"
        return eff

    def describe(self) -> dict[str, Any]:
        """脱敏视图（GET）：key 只回 has_api_key / 来源，绝不回明文。"""
        eff = self.effective()
        return {
            "provider": eff["provider"],
            "base_url": eff["base_url"],
            "model_name": eff["model_name"],
            "has_api_key": bool(eff["api_key"]),
            "api_key_source": eff["api_key_source"],
            "configured": eff["provider"] != "mock" or bool(eff["api_key"]),
        }

    def to_settings(self) -> Settings:
        """把生效配置做成 Settings 快照（供 build_provider / 热重载装配）。"""
        eff = self.effective()
        return self._settings.model_copy(
            update={
                "model_provider": eff["provider"],
                "model_api_key": eff["api_key"],
                "model_base_url": eff["base_url"],
                "model_name": eff["model_name"],
            }
        )

    # ---------- 写入 ----------

    def save(self, data: dict[str, Any]) -> dict[str, Any]:
        """部分更新并落盘。

        - provider / base_url / model_name：空串或 None 忽略（保持现有）
        - api_key：空串 -> 清除；非空 -> 覆盖（明文仅存服务端文件）
        校验失败抛 ValidationError（A4 契约，REST 400）。
        """
        cur = self._load()
        for field in ("provider", "base_url", "model_name"):
            val = data.get(field)
            if isinstance(val, str) and val.strip():
                cur[field] = val.strip()
        if "api_key" in data:
            val = data.get("api_key")
            if val is None:
                pass
            elif val == "":
                cur.pop("api_key", None)  # 清除已存 key
            else:
                cur["api_key"] = val

        provider = cur.get("provider", self._settings.model_provider)
        if provider not in _VALID_PROVIDERS:
            raise ValidationError(f"未知 model_provider: {provider!r}（可选 mock|openai）")
        base_url = cur.get("base_url", self._settings.model_base_url)
        if base_url and not base_url.startswith(("http://", "https://")):
            raise ValidationError("base_url 必须以 http(s):// 开头")
        if provider == "openai" and not cur.get("model_name"):
            raise ValidationError("接入真实模型时 model_name 不能为空")

        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_name(self._path.name + ".tmp")
        tmp.write_text(json.dumps(cur, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self._path)
        # key 明文仅本用户可读（Windows 下 chmod 为 no-op）
        with contextlib.suppress(OSError):
            os.chmod(self._path, 0o600)
        return self.describe()
