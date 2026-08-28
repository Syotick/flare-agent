"""运维 API（M6）：SLO 状态 / 错误预算快照，供控制台、告警检查与发布门禁复用。

数据源：进程内指标注册表（HTTP 中间件 + 任务收尾埋点写入）。
生产替换：/v1/ops/slo 直接读 Prometheus/PG 聚合，形状保持一致即可。
"""

from __future__ import annotations

import time

from fastapi import APIRouter

from flare_common import metrics
from flare_common.config import Settings
from flare_common.slo import slo_report


def _build_report(settings: Settings) -> dict:
    snap = metrics.snapshot()
    req = snap["http_requests_total"]
    task = snap["task_runs_total"]
    return slo_report(
        availability_target=settings.slo_availability,
        period_seconds=settings.slo_period_days * 86400,
        total_ok=req["success"],
        total_bad=max(req["total"] - req["success"], 0),
        task_ok=task["succeeded"],
        task_bad=task["errored"],
        p95_latency=snap["http_request_duration_seconds"]["p95"],
        latency_target=settings.slo_p95_latency_seconds,
    )


def build_ops_router(settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/v1/ops", tags=["ops"])

    @router.get("/slo")
    async def slo_status() -> dict:
        report = _build_report(settings)
        return {
            "overall": report["overall"],
            "generated_at": int(time.time()),
            "period_days": settings.slo_period_days,
            "slos": report["slos"],
        }

    @router.get("/error-budget")
    async def error_budget() -> dict:
        report = _build_report(settings)
        return {
            "period_days": settings.slo_period_days,
            "budgets": [
                {"name": r["name"], "budget": r["budget"]} for r in report["slos"] if "budget" in r
            ],
        }

    return router
