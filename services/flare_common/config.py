"""全局配置（12-factor：全部来自环境变量，前缀 FLARE_）。

示例：FLARE_ENV / FLARE_DATABASE_URL / FLARE_MODEL_PROVIDER
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置。env_file=.env 仅在本地开发加载；生产全部走环境变量。"""

    model_config = SettingsConfigDict(env_prefix="FLARE_", env_file=".env", extra="ignore")

    app_name: str = "flare-agent"
    env: str = "dev"
    log_level: str = "INFO"

    database_url: str = "postgresql://flare:flare@localhost:5432/flare"
    redis_url: str = "redis://localhost:6379/0"

    object_store_endpoint: str = "http://localhost:9000"
    object_store_access_key: str = "minioadmin"
    object_store_secret_key: str = "minioadmin"

    model_provider: str = "mock"
    model_api_key: str = ""
    model_base_url: str = "http://localhost:9001/v1"


@lru_cache
def get_settings() -> Settings:
    """进程内单例配置。"""
    return Settings()
