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

    # M5：任务存储（memory|sqlite|redis）；OTel 导出端点（空=不启用）
    task_store: str = "memory"
    otel_endpoint: str = ""

    # M6：SLO 目标（错误预算/告警依据；生产用环境变量覆盖，如 FLARE_SLO_AVAILABILITY=0.99）
    slo_availability: float = 0.99
    slo_p95_latency_seconds: float = 5.0
    slo_period_days: int = 30

    # FR-2/FR-3：MCP 服务器列表（JSON）+ 技能库目录
    # FLARE_MCP_SERVERS='[{"name":"echo","url":"http://localhost:9001/mcp","transport":"streamable_http","headers":{},"enabled":true}]'
    mcp_servers: list[dict] = []
    skills_dir: str = "data/skills"

    # F9.3：OpenAI 兼容 API 认证（FLARE_API_KEY；空=不校验，生产务必配置）
    api_key: str = ""


@lru_cache
def get_settings() -> Settings:
    """进程内单例配置。"""
    return Settings()
