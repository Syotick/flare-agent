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

    # 供应商：mock | openai | anthropic（Claude 原生）；openai 兼容 DashScope/DeepSeek
    model_provider: str = "mock"
    model_api_key: str = ""
    model_base_url: str = "http://localhost:9001/v1"  # 本地 vLLM 默认端口
    model_name: str = "gpt-4o-mini"
    # 模型设置页（控制台「模型」）本地持久化位置；真实环境变量优先于该文件
    model_config_path: str = "data/model_config.json"

    # M5：任务存储（memory|sqlite|redis）；OTel 导出端点（空=不启用）
    # DSH 对齐：本地默认 sqlite 落盘（data/tasks.sqlite3）——会话列表重启可查；
    # 生产多实例用 redis（FLARE_TASK_STORE=redis）
    task_store: str = "sqlite"
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

    # F1.3/F2.4：审批策略（等于或高于该级别的工具需人工审批；默认 destructive 起）
    # 例如 FLARE_APPROVAL_REQUIRE_LEVEL=write 则所有写/破坏性工具都要审批
    approval_require_level: str = "destructive"
    approval_timeout: float = 300.0  # 审批等待超时（秒），超时自动按拒绝处理
    # 审批后端：local（进程内，默认/单实例）| redis（多实例共享，跨节点决策轮询唤醒）
    approval_backend: str = "local"
    # TOFU（首用信任）：同作用域某工具获批一次后后续自动放行，防审批疲劳
    approval_tofu: bool = True
    approval_tofu_scope: str = "thread"  # thread（会话线程，默认）| tenant | off


@lru_cache
def get_settings() -> Settings:
    """进程内单例配置。"""
    return Settings()
