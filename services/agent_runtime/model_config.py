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
import uuid
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
        "models": ["claude-sonnet-5", "claude-opus-5", "claude-fable-5", "claude-haiku-5"],
    },
    {
        "id": "openai",
        "name": "OpenAI",
        "provider": "openai",
        "base_url": "https://api.openai.com/v1",
        "models": ["gpt-5.4", "gpt-5.2", "gpt-5.1", "gpt-5", "gpt-4.1", "gpt-4o-mini"],
    },
    {
        "id": "deepseek",
        "name": "DeepSeek",
        "provider": "openai",
        "base_url": "https://api.deepseek.com/v1",
        "models": ["deepseek-v4-flash", "deepseek-v4-pro"],
    },
    {
        "id": "dashscope",
        "name": "通义千问（阿里云百炼）",
        "provider": "openai",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "models": ["qwen-max", "qwen-plus", "qwen3-max", "qwen3-plus", "qwen-turbo"],
    },
    {
        "id": "siliconflow",
        "name": "硅基流动",
        "provider": "openai",
        "base_url": "https://api.siliconflow.cn/v1",
        "models": [
            "Qwen/Qwen3-235B-A22B",
            "deepseek-ai/DeepSeek-V3.2",
            "THUDM/GLM-4.6",
        ],
    },
    {
        "id": "ollama",
        "name": "Ollama（本地）",
        "provider": "openai",
        "base_url": "http://localhost:11434/v1",
        "models": ["llama4:70b", "qwen3:32b", "deepseek-v3.2:32b"],
    },
    {
        "id": "vllm",
        "name": "vLLM（本地）",
        "provider": "openai",
        "base_url": "http://localhost:8000/v1",
        "models": ["Qwen3-32B-Instruct"],
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


def _normalize_models(raw: Any) -> list[str]:
    """模型目录：接受 list[str]；非列表按空处理，元素去空白去空、去重。"""
    if not isinstance(raw, list):
        return []
    seen: list[str] = []
    for m in raw:
        s = str(m).strip()
        if s and s not in seen:
            seen.append(s)
    return seen


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

    # ---------- 自定义供应商（profiles） ----------
    # 独立文件 data/model_profiles.json：用户自建供应商，可保存多个、随时切换激活。
    # 与全局生效配置分离：激活仍走 save()（写主配置），profiles 只是可复用的配置集。

    @property
    def _profiles_path(self) -> Path:
        return self._path.with_name("model_profiles.json")

    def _load_profiles(self) -> list[dict[str, Any]]:
        try:
            raw = json.loads(self._profiles_path.read_text(encoding="utf-8"))
            return raw.get("profiles", []) if isinstance(raw, dict) else []
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return []

    def _write_profiles(self, profiles: list[dict[str, Any]]) -> None:
        self._profiles_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._profiles_path.with_name(self._profiles_path.name + ".tmp")
        tmp.write_text(
            json.dumps({"profiles": profiles}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp.replace(self._profiles_path)
        with contextlib.suppress(OSError):
            os.chmod(self._profiles_path, 0o600)

    @staticmethod
    def _sanitize_profile(profile: dict[str, Any]) -> dict[str, Any]:
        """脱敏视图：key 只回 has_api_key；模型目录（models）原样回。"""
        return {
            "id": profile["id"],
            "name": profile["name"],
            "provider": profile["provider"],
            "base_url": profile["base_url"],
            "model_name": profile["model_name"],
            "models": list(profile.get("models") or []),
            "has_api_key": bool(profile.get("api_key")),
        }

    @staticmethod
    def _validate_profile(name: str, provider: str, base_url: str, model_name: str) -> None:
        if not name.strip():
            raise ValidationError("供应商名称不能为空")
        if provider not in _VALID_PROVIDERS:
            raise ValidationError(
                f"未知 model_provider: {provider!r}（可选 {'|'.join(_VALID_PROVIDERS)}）"
            )
        if base_url and not base_url.startswith(("http://", "https://")):
            raise ValidationError("base_url 必须以 http(s):// 开头")
        if provider in ("openai", "anthropic") and not model_name.strip():
            raise ValidationError("接入真实模型时 model_name 不能为空")

    def list_profiles(self) -> list[dict[str, Any]]:
        """脱敏列表：key 只回 has_api_key。"""
        return [self._sanitize_profile(p) for p in self._load_profiles()]

    def save_profile(self, data: dict[str, Any]) -> dict[str, Any]:
        """新建或更新自定义供应商。

        - 带 id = 更新（部分更新：缺失字段沿用已有值）；不带 = 新建（全字段必填）
        - api_key：非空 -> 覆盖；空串 / 缺省 -> 保持已有 key（不回传明文）
        """
        profiles = self._load_profiles()
        pid = data.get("id")
        if pid:
            cur = next((p for p in profiles if p["id"] == pid), None)
            if cur is None:
                raise ValidationError(f"供应商不存在: {pid}")
            for field in ("name", "provider", "base_url", "model_name"):
                val = data.get(field)
                if isinstance(val, str) and val.strip():
                    cur[field] = val.strip()
        else:
            name = (data.get("name") or "").strip()
            provider = (data.get("provider") or "").strip()
            base_url = (data.get("base_url") or "").strip()
            model_name = (data.get("model_name") or "").strip()
            self._validate_profile(name, provider, base_url, model_name)
            pid = "p_" + uuid.uuid4().hex[:10]
            cur = {
                "id": pid,
                "name": name,
                "provider": provider,
                "base_url": base_url,
                "model_name": model_name,
                "models": _normalize_models(data.get("models")),
            }
            profiles.append(cur)
        # 合并后完整性校验（更新后也不允许缺关键字段）
        self._validate_profile(cur["name"], cur["provider"], cur["base_url"], cur["model_name"])
        if "models" in data:
            cur["models"] = _normalize_models(data.get("models"))
        if data.get("api_key"):  # 仅非空覆盖；空串/缺省保持已有 key
            cur["api_key"] = data["api_key"]
        self._write_profiles(profiles)
        return self._sanitize_profile(cur)

    def delete_profile(self, profile_id: str) -> None:
        profiles = self._load_profiles()
        remaining = [p for p in profiles if p["id"] != profile_id]
        if len(remaining) == len(profiles):
            raise ValidationError(f"供应商不存在: {profile_id}")
        self._write_profiles(remaining)
