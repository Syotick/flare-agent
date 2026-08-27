"""OpenTelemetry 接入点（M5 接入导出器；当前为本地 Tracer 占位）。"""

from __future__ import annotations

from opentelemetry import trace

_tracer = trace.get_tracer("flare-agent")


def get_tracer() -> trace.Tracer:
    """获取应用级 Tracer。"""
    return _tracer
