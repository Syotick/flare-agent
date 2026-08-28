"""SLO / 错误预算 / 告警分级（M6）：纯函数可测。

- SLO：可用性/成功率目标（如 99.9%）+ 周期（默认 30 天）；
- 错误预算：允许失败数 = total * (1 - target)；消耗比 = bad / 预算；
- 燃烧速率（burn rate）：窗口内预算消耗比例折算到"预算耗尽需要多久"；
- 多窗口告警（Google SRE 简化版）：慢窗口(1h)持续烧穿 -> P2 预警 / 快到 P1，
  快窗口(5m)高速烧穿 -> 立即 P1；预算整体耗尽 -> P1。
"""

from __future__ import annotations

from dataclasses import dataclass

# 告警级别（对外稳定）
SEV_NONE = "none"
SEV_WARNING = "warning"
SEV_CRITICAL = "critical"


@dataclass(frozen=True)
class SLO:
    name: str
    target: float  # 0~1 目标（可用性/成功率）
    period_seconds: int = 30 * 86400
    description: str = ""


@dataclass(frozen=True)
class Observation:
    """一个窗口内的观测：total 总事件数，bad 违反 SLO 的事件数。"""

    total: int
    bad: int
    window_seconds: int


@dataclass(frozen=True)
class Alert:
    severity: str  # critical | warning | none
    name: str
    message: str

    @property
    def triggered(self) -> bool:
        return self.severity != SEV_NONE


def error_budget(slo: SLO, total: int, bad: int) -> dict:
    """错误预算快照：允许失败数、消耗比、剩余比。"""
    budget = max(total * (1.0 - slo.target), 0.0)
    consumed = bad / budget if budget > 0 else (1.0 if bad > 0 else 0.0)
    return {
        "slo": slo.name,
        "target": slo.target,
        "total": total,
        "bad": bad,
        "budget": round(budget, 3),
        "consumed_ratio": round(consumed, 6),
        "remaining_ratio": round(max(1.0 - consumed, 0.0), 6),
    }


def burn_rate(slo: SLO, window: Observation) -> float:
    """燃烧速率：窗口消耗比例 / (窗口/周期)。1x = 正好在周期末耗尽预算。"""
    consumed = error_budget(slo, window.total, window.bad)["consumed_ratio"]
    frac = window.window_seconds / slo.period_seconds if slo.period_seconds > 0 else 0.0
    return consumed / frac if frac > 0 else 0.0


def classify_burn(
    slo: SLO,
    window: Observation,
    warn_burn: float = 14.4,
    critical_burn: float = 36.0,
) -> Alert:
    """单窗口燃烧速率分级：>=36x -> critical，>=14.4x -> warning。"""
    rate = burn_rate(slo, window)
    if rate >= critical_burn:
        sev, why = SEV_CRITICAL, f"燃烧速率 {rate:.1f}x >= {critical_burn:.0f}x"
    elif rate >= warn_burn:
        sev, why = SEV_WARNING, f"燃烧速率 {rate:.1f}x >= {warn_burn:.1f}x"
    else:
        sev, why = SEV_NONE, f"燃烧速率 {rate:.1f}x 正常"
    return Alert(
        sev,
        slo.name,
        f"{slo.name}: {why}（窗口 {window.window_seconds}s，bad={window.bad}/{window.total}）",
    )


def classify_multi(
    slo: SLO,
    fast: Observation,
    slow: Observation,
    fast_critical_burn: float = 36.0,
    slow_warn_burn: float = 14.4,
    slow_critical_burn: float = 36.0,
) -> Alert:
    """多窗口燃烧速率告警（Google SRE 简化版）。

    - 快窗口(5m)高速烧穿 -> critical（说明刚出问题，等不到慢窗口）；
    - 慢窗口(1h)持续烧穿 -> warning；持续更猛 -> critical；
    - 任一口径 critical 优先于 warning。
    """
    fast_rate = burn_rate(slo, fast)
    slow_rate = burn_rate(slo, slow)
    if fast_rate >= fast_critical_burn or slow_rate >= slow_critical_burn:
        sev, why = SEV_CRITICAL, f"fast={fast_rate:.1f}x slow={slow_rate:.1f}x"
    elif slow_rate >= slow_warn_burn:
        sev, why = SEV_WARNING, f"slow={slow_rate:.1f}x"
    else:
        sev, why = SEV_NONE, f"fast={fast_rate:.1f}x slow={slow_rate:.1f}x"
    return Alert(
        sev,
        slo.name,
        f"{slo.name}: {why}（窗口 fast={fast.window_seconds}s slow={slow.window_seconds}s）",
    )


def check_latency(target_p95: float, p95: float | None, name: str = "latency") -> Alert:
    """延迟 SLO：p95 超目标 -> critical（超得越多越严重）；无观测 -> none。"""
    if p95 is None:
        return Alert(SEV_NONE, name, f"{name}: 暂无观测")
    if p95 > target_p95:
        return Alert(
            SEV_CRITICAL,
            name,
            f"{name}: p95={p95:.3f}s 超过目标 {target_p95}s（{p95 / target_p95:.2f}x）",
        )
    return Alert(SEV_NONE, name, f"{name}: p95={p95:.3f}s <= 目标 {target_p95}s")


def slo_report(
    availability_target: float,
    period_seconds: int,
    total_ok: int,
    total_bad: int,
    task_ok: int,
    task_bad: int,
    p95_latency: float | None,
    latency_target: float,
) -> dict:
    """把指标快照换算成运维报告（/v1/ops/slo 主输出）。

    三个 SLO：API 可用性（HTTP 非 4xx/5xx 率）、任务成功率、延迟 p95。
    """
    availability = SLO("api_availability", availability_target, period_seconds)
    tasks = SLO("task_success", availability_target, period_seconds)

    def as_window(ok: int, bad: int, window: int) -> Observation:
        return Observation(total=ok + bad, bad=bad, window_seconds=window)

    # 以"自观测以来"整段作为慢窗口（观测总时长由 period 折算），无真窗口则用 1h 近似展示
    avail_obs = as_window(total_ok, total_bad, min(period_seconds, 3600))
    task_obs = as_window(task_ok, task_bad, min(period_seconds, 3600))
    latency_alert = check_latency(latency_target, p95_latency)
    reports = [
        {
            "name": availability.name,
            "target": availability.target,
            "budget": error_budget(availability, avail_obs.total, avail_obs.bad),
            "alert": classify_burn(availability, avail_obs),
        },
        {
            "name": tasks.name,
            "target": tasks.target,
            "budget": error_budget(tasks, task_obs.total, task_obs.bad),
            "alert": classify_burn(tasks, task_obs),
        },
        {
            "name": latency_alert.name,
            "target": latency_target,
            "p95": p95_latency,
            "alert": latency_alert,
        },
    ]
    severities = [r["alert"].severity for r in reports]
    overall = (
        SEV_CRITICAL
        if SEV_CRITICAL in severities
        else (SEV_WARNING if SEV_WARNING in severities else SEV_NONE)
    )
    return {"overall": overall, "slos": reports}


def highest_severity(alerts: list[Alert]) -> str:
    """多个告警取最高级别。"""
    if any(a.severity == SEV_CRITICAL for a in alerts):
        return SEV_CRITICAL
    if any(a.severity == SEV_WARNING for a in alerts):
        return SEV_WARNING
    return SEV_NONE
