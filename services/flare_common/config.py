"""全局配置（12-factor：全部来自环境变量，前缀 FLARE_）。

示例：FLARE_ENV / FLARE_DATABASE_URL / FLARE_MODEL_PROVIDER
extra="forbid"：拼错的环境变量在启动即报错，绝不静默沿用默认值（fail-fast）。
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置。env_file=.env 仅在本地开发加载；生产全部走环境变量。"""

    model_config = SettingsConfigDict(env_prefix="FLARE_", env_file=".env", extra="forbid")

    app_name: str = "flare-agent"
    env: str = "dev"
    log_level: str = "INFO"

    # CORS：dev 默认放开；生产用 JSON 数组，如 FLARE_CORS_ORIGINS='["https://app.example.com"]'
    cors_origins: list[str] = ["*"]

    database_url: str = "postgresql://flare:flare@localhost:5432/flare"
    redis_url: str = "redis://localhost:6379/0"

    object_store_endpoint: str = "http://localhost:9000"
    object_store_access_key: str = "minioadmin"
    object_store_secret_key: str = "minioadmin"

    model_provider: str = "mock"  # mock | openai（OpenAI 兼容；DashScope/DeepSeek 走同协议）
    model_api_key: str = ""
    model_base_url: str = "http://localhost:9001/v1"  # 本地 vLLM 默认端口
    model_name: str = "gpt-4o-mini"


@lru_cache
def get_settings() -> Settings:
    """进程内单例配置。"""
    return Settings()
