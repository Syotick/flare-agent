"""Prometheus 文本格式指标（M6）：纯 Python 零外部依赖。

- Counter / Gauge / Histogram 最小实现 + Registry.render() 输出 text exposition format v0.0.4；
- 供 /metrics 端点、SLO 状态、压测分析复用；
- 生产可换用 prometheus_client，接口形状保持一致（observe/inc/set/quantile）。
"""

from __future__ import annotations

import re
from collections.abc import Iterable

_SANITIZE = re.compile(r"[^a-zA-Z0-9_]")


def _clean_name(name: str) -> str:
    return _SANITIZE.sub("_", name)


def _esc_label(value: object) -> str:
    """Prometheus 标签值转义：反斜杠/双引号/换行。

    用 chr(92)/chr(10) 表示反斜杠与换行，避免源码里多层转义出错。
    """
    s = str(value)
    bs = chr(92)
    return s.replace(bs, bs + bs).replace('"', bs + '"').replace(chr(10), bs + "n")


class Counter:
    """单调递增计数器；labelnames 为固定标签键（顺序与传入一致）。"""

    def __init__(self, name: str, help: str = "", labelnames: tuple[str, ...] = ()):
        self.name = _clean_name(name)
        self.help = help
        self.labelnames = labelnames
        self._values: dict[tuple[str, ...], float] = {}

    def _key(self, labels: dict[str, object]) -> tuple[str, ...]:
        if len(labels) != len(self.labelnames):
            raise ValueError(f"{self.name}: 需要标签 {self.labelnames}，收到 {tuple(labels)}")
        return tuple(str(labels[k]) for k in self.labelnames)

    def inc(self, amount: float = 1.0, **labels: object) -> None:
        if amount < 0:
            raise ValueError(f"{self.name}: 计数器不能自减 amount={amount}")
        key = self._key(labels)
        self._values[key] = self._values.get(key, 0.0) + amount

    def set(self, value: float, **labels: object) -> None:
        self._values[self._key(labels)] = value

    def get(self, **labels: object) -> float:
        return self._values.get(self._key(labels), 0.0)

    def samples(self) -> Iterable[tuple[tuple[str, ...], float]]:
        return sorted(self._values.items())


class Gauge(Counter):
    """可增可减的瞬时值（复用 Counter 存储，语义由调用方把握）。"""

    def inc(self, amount: float = 1.0, **labels: object) -> None:
        key = self._key(labels)
        self._values[key] = self._values.get(key, 0.0) + amount


class Histogram:
    """直方图：固定桶 + 计数/和；quantile 按桶线性插值（histogram_quantile 同法）。"""

    _DEFAULT_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

    def __init__(
        self,
        name: str,
        help: str = "",
        buckets: tuple[float, ...] = _DEFAULT_BUCKETS,
        labelnames: tuple[str, ...] = (),
    ) -> None:
        self.name = _clean_name(name)
        self.help = help
        self.buckets = tuple(sorted(buckets))
        self.labelnames = labelnames
        self._count: dict[tuple[str, ...], float] = {}
        self._sum: dict[tuple[str, ...], float] = {}
        self._buckets: dict[tuple[str, ...], list[float]] = {}

    def _key(self, labels: dict[str, object]) -> tuple[str, ...]:
        if len(labels) != len(self.labelnames):
            raise ValueError(f"{self.name}: 需要标签 {self.labelnames}，收到 {tuple(labels)}")
        return tuple(str(labels[k]) for k in self.labelnames)

    def observe(self, value: float, **labels: object) -> None:
        if value < 0:
            raise ValueError(f"{self.name}: 观测值不能为负 value={value}")
        key = self._key(labels)
        self._count[key] = self._count.get(key, 0.0) + 1
        self._sum[key] = self._sum.get(key, 0.0) + value
        buckets = self._buckets.setdefault(key, [0.0] * len(self.buckets))
        for i, upper in enumerate(self.buckets):
            if value <= upper:
                buckets[i] += 1.0

    def count(self, **labels: object) -> float:
        return self._count.get(self._key(labels), 0.0)

    def sum(self, **labels: object) -> float:
        return self._sum.get(self._key(labels), 0.0)

    def quantile(self, q: float, **labels: object) -> float | None:
        """按桶直方图近似分位数（Prometheus histogram_quantile 同法）。"""
        key = self._key(labels)
        total = self._count.get(key, 0.0)
        if total <= 0:
            return None
        rank = q * total
        cumulative = 0.0
        prev = 0.0
        for upper, bucket in zip(self.buckets, self._buckets.get(key, []), strict=False):
            cumulative = bucket if bucket > 0 else cumulative
            if cumulative >= rank:
                width = upper - prev
                frac = 0.0
                if bucket > 0:
                    below = cumulative - bucket
                    frac = (rank - below) / bucket
                return prev + width * min(max(frac, 0.0), 1.0)
            prev = upper
        return self.buckets[-1] if self.buckets else None


class Registry:
    def __init__(self) -> None:
        self._metrics: list[Counter | Histogram] = []

    def register(self, metric: Counter | Histogram) -> Counter | Histogram:
        if any(m.name == metric.name for m in self._metrics):
            raise ValueError(f"指标已注册: {metric.name}")
        self._metrics.append(metric)
        return metric

    def counter(self, name: str, help: str = "", labelnames: tuple[str, ...] = ()) -> Counter:
        return self.register(Counter(name, help, labelnames))

    def gauge(self, name: str, help: str = "", labelnames: tuple[str, ...] = ()) -> Gauge:
        return self.register(Gauge(name, help, labelnames))

    def histogram(
        self,
        name: str,
        help: str = "",
        buckets: tuple[float, ...] = Histogram._DEFAULT_BUCKETS,
        labelnames: tuple[str, ...] = (),
    ) -> Histogram:
        return self.register(Histogram(name, help, buckets, labelnames))

    def render(self) -> str:
        """渲染 Prometheus text exposition format v0.0.4。"""
        out: list[str] = []
        for m in self._metrics:
            out.append(f"# HELP {m.name} {m.help}")
            if isinstance(m, Histogram):
                out.append(f"# TYPE {m.name} histogram")
                for key in sorted(m._count.keys()):
                    labels = self._fmt_labels(m, key)
                    for i, upper in enumerate(m.buckets):
                        le = "+Inf" if upper == float("inf") else str(upper)
                        line = f"{m.name}_bucket{self._le_labels(labels, le)}"
                        out.append(f"{line} {int(m._buckets[key][i])}")
                    out.append(f"{m.name}_sum{labels} {m._sum[key]:.6g}")
                    out.append(f"{m.name}_count{labels} {int(m._count[key])}")
            else:
                mtype = "gauge" if isinstance(m, Gauge) else "counter"
                out.append(f"# TYPE {m.name} {mtype}")
                for key, value in m.samples():
                    out.append(f"{m.name}{self._fmt_labels(m, key)} {value:.6g}")
        return chr(10).join(out) + chr(10)

    @staticmethod
    def _fmt_labels(m: Counter | Histogram, key: tuple[str, ...]) -> str:
        if not m.labelnames:
            return ""
        pairs = ",".join(f'{n}="{_esc_label(v)}"' for n, v in zip(m.labelnames, key, strict=True))
        return "{" + pairs + "}"

    @staticmethod
    def _le_labels(labels: str, le: str) -> str:
        """给直方图 _bucket 追加 le 标签（合并既有标签）。"""
        if not labels:
            return '{le="' + le + '"}'
        inner = labels[1:-1]
        return "{" + inner + ',le="' + le + '"}'


# ---------------------------------------------------------------------------
# 应用级指标（默认注册表；服务启动即注册，进程内单例）
# ---------------------------------------------------------------------------
METRICS = Registry()

http_requests_total = METRICS.counter(
    "flare_http_requests_total", "HTTP 请求总数（按方法/路径/状态）", ("method", "path", "status")
)
http_request_duration_seconds = METRICS.histogram(
    "flare_http_request_duration_seconds", "HTTP 请求耗时（秒）"
)
task_runs_total = METRICS.counter(
    "flare_task_runs_total", "Agent 任务执行数（按结果）", ("outcome",)
)
task_duration_seconds = METRICS.histogram(
    "flare_task_duration_seconds", "Agent 任务端到端耗时（秒）"
)


def observe_http(method: str, path: str, status: int, duration: float) -> None:
    """HTTP 中间件埋点：计数 + 耗时。"""
    http_requests_total.inc(1.0, method=method, path=path, status=str(status))
    http_request_duration_seconds.observe(duration)


def observe_task(outcome: str, duration: float) -> None:
    """任务收尾埋点：结果分类 + 端到端耗时。"""
    task_runs_total.inc(1.0, outcome=outcome)
    task_duration_seconds.observe(duration)


def snapshot() -> dict:
    """当前指标快照（供 /v1/ops/slo 与压测分析）。"""
    ok_requests = sum(
        v for k, v in http_requests_total.samples() if not k[2].startswith(("5", "4"))
    )
    total_requests = sum(v for _, v in http_requests_total.samples())
    tasks_ok = task_runs_total.get(outcome="succeeded")
    tasks_bad = task_runs_total.get(outcome="errored")
    return {
        "http_requests_total": {
            "total": total_requests,
            "success": ok_requests,
            "by_status": {k[2]: v for k, v in http_requests_total.samples()},
        },
        "http_request_duration_seconds": {
            "p50": http_request_duration_seconds.quantile(0.5),
            "p95": http_request_duration_seconds.quantile(0.95),
            "p99": http_request_duration_seconds.quantile(0.99),
            "count": http_request_duration_seconds.count(),
        },
        "task_runs_total": {
            "succeeded": tasks_ok,
            "errored": tasks_bad,
            "total": tasks_ok + tasks_bad,
        },
        "task_duration_seconds": {
            "p50": task_duration_seconds.quantile(0.5),
            "p95": task_duration_seconds.quantile(0.95),
            "count": task_duration_seconds.count(),
        },
    }


def render_metrics() -> str:
    return METRICS.render()
