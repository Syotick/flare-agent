"""OpenTelemetry（M5）：可观测性埋点 + OTLP 导出。

- 无端点：no-op（不装导出器、不引入依赖负担），本地开发零成本；
- 有端点：装 OTLP HTTP 导出器（BatchSpanProcessor），缺 SDK -> OTelUnavailableError fail-fast；
- 生产：端点指向 OTel Collector（ACK/ARMS），导出 traces。
"""

from __future__ import annotations

from flare_common.errors import FlareError


class OTelUnavailableError(FlareError):
    code = "OTEL_UNAVAILABLE"
    status_code = 503


_initialized = False


def init_tracing(
    service_name: str,
    endpoint: str | None = None,
    exporter_factory=None,
) -> bool:
    """初始化 tracing。

    返回 True 表示已启用导出；endpoint 为空时返回 False（no-op）。
    exporter_factory 仅供测试/替换导出器（默认 OTLP HTTP）。
    """
    global _initialized  # noqa: PLW0603
    if _initialized:
        return True
    if not endpoint:
        return False
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import SERVICE_NAME, Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError as exc:
        raise OTelUnavailableError(
            f"已配置 OTel 端点但缺少 SDK：{exc}（pip install opentelemetry-sdk otlp-exporter）"
        ) from exc
    provider = TracerProvider(resource=Resource.create({SERVICE_NAME: service_name}))
    factory = exporter_factory or OTLPSpanExporter
    exporter = factory(endpoint=endpoint.rstrip("/") + "/v1/traces")
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _initialized = True
    return True


def get_tracer():
    """获取应用 tracer（埋点用）。未初始化时返回 no-op tracer。"""
    from opentelemetry import trace

    return trace.get_tracer("flare-agent")
