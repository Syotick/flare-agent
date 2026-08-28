"""M6 生产运营：指标注册表 / SLO 错误预算 / 告警分级 / 压测分析 / 发布门禁 / 运维 API。"""

from __future__ import annotations

from fastapi.testclient import TestClient
from scripts.loadtest import analyze
from scripts.release_gate import evaluate_gate

from agent_runtime.app import create_app
from flare_common.metrics import Counter, Histogram, Registry
from flare_common.slo import (
    SEV_CRITICAL,
    SEV_NONE,
    SEV_WARNING,
    SLO,
    Alert,
    Observation,
    burn_rate,
    check_latency,
    classify_burn,
    classify_multi,
    error_budget,
    highest_severity,
    slo_report,
)

TARGET = 0.99
PERIOD = 30 * 86400
SLO30 = SLO("avail", TARGET, PERIOD)


# ---------------------------------------------------------------------------
# metrics：计数器 / 直方图 / 文本格式
# ---------------------------------------------------------------------------


def test_counter_inc_and_get() -> None:
    c = Counter("test_counter_total", "t")
    c.inc(3)
    c.inc(2)
    assert c.get() == 5


def test_counter_label_enforcement() -> None:
    c = Counter("test_labeled_total", "", ("method",))
    c.inc(1, method="GET")
    assert c.get(method="GET") == 1
    try:
        c.inc(1)  # 缺标签应报错
        raise AssertionError("should have raised")
    except ValueError:
        pass


def test_histogram_quantile_and_bucket_counts() -> None:
    h = Histogram("test_lat_seconds", "", buckets=(0.1, 1.0, 5.0))
    h.observe(0.05)
    h.observe(0.5)
    h.observe(3.0)
    assert h.count() == 3
    assert round(h.sum(), 3) == 3.55
    assert h.quantile(0.5) is not None
    assert h.quantile(0.99) <= 5.0
    assert Histogram("h_empty_seconds", "").quantile(0.5) is None  # 无观测 -> None


def test_registry_render_text_format() -> None:
    reg = Registry()
    c = reg.counter("demo_total", "demo counter")
    c.inc(4)
    h = reg.histogram("demo_seconds", "demo hist", buckets=(1.0, 2.0))
    h.observe(0.5)
    text = reg.render()
    assert "# HELP demo_total demo counter" in text
    assert "# TYPE demo_total counter" in text
    assert "demo_total 4" in text
    assert "# TYPE demo_seconds histogram" in text
    assert 'demo_seconds_bucket{le="1.0"} 1' in text
    assert 'demo_seconds_bucket{le="2.0"} 1' in text
    assert "demo_seconds_count 1" in text


def test_registry_render_escapes_labels() -> None:
    reg = Registry()
    c = reg.counter("esc_total", "", ("k",))
    c.inc(1, k='a"b')
    assert 'k="a\\"b"' in reg.render()


# ---------------------------------------------------------------------------
# SLO：错误预算 / 燃烧速率 / 告警分级
# ---------------------------------------------------------------------------


def test_error_budget_math() -> None:
    eb = error_budget(SLO30, total=1000, bad=10)  # 预算=10，恰好用完
    assert eb["budget"] == 10.0
    assert eb["consumed_ratio"] == 1.0
    eb2 = error_budget(SLO30, total=1000, bad=5)
    assert eb2["remaining_ratio"] == 0.5


def test_burn_rate_1x_is_period_end() -> None:
    # 整段周期内恰好耗尽预算 -> 燃烧速率 1x
    window = Observation(total=1000, bad=10, window_seconds=PERIOD)
    assert round(burn_rate(SLO30, window), 3) == 1.0


def test_classify_burn_levels() -> None:
    none = classify_burn(SLO30, Observation(100000, 1, 300))  # 低速率
    warn = classify_burn(SLO30, Observation(100000, 20, 3600))  # 中高速率
    crit = classify_burn(SLO30, Observation(1000, 50, 300))  # 高速烧穿
    assert none.severity == SEV_NONE
    assert warn.severity == SEV_WARNING
    assert crit.severity == SEV_CRITICAL
    assert not none.triggered
    assert crit.triggered


def test_classify_multi_fast_burn_wins() -> None:
    fast = Observation(1000, 50, 300)  # 快窗口高速烧穿
    slow = Observation(100000, 20, 3600)  # 慢窗口正常
    alert = classify_multi(SLO30, fast, slow)
    assert alert.severity == SEV_CRITICAL


def test_classify_multi_slow_warn() -> None:
    fast = Observation(100000, 1, 300)
    slow = Observation(1000000, 200, 3600)  # 慢窗口 burn=14.4x
    alert = classify_multi(SLO30, fast, slow)
    assert alert.severity == SEV_WARNING


def test_check_latency_and_highest_severity() -> None:
    assert check_latency(5.0, 7.0).severity == SEV_CRITICAL
    assert check_latency(5.0, 1.0).severity == SEV_NONE
    assert check_latency(5.0, None).severity == SEV_NONE
    assert highest_severity([Alert(SEV_NONE, "a", ""), Alert(SEV_WARNING, "b", "")]) == SEV_WARNING
    assert (
        highest_severity([Alert(SEV_WARNING, "a", ""), Alert(SEV_CRITICAL, "b", "")])
        == SEV_CRITICAL
    )


def test_slo_report_structure() -> None:
    report = slo_report(
        availability_target=TARGET,
        period_seconds=PERIOD,
        total_ok=99_999,
        total_bad=1,
        task_ok=9_999,
        task_bad=0,
        p95_latency=0.4,
        latency_target=5.0,
    )
    assert report["overall"] == SEV_NONE
    assert len(report["slos"]) == 3
    names = [s["name"] for s in report["slos"]]
    assert names == ["api_availability", "task_success", "latency"]


# ---------------------------------------------------------------------------
# 压测分析 / 发布门禁 / 运维 API
# ---------------------------------------------------------------------------


def test_loadtest_analyze_pass() -> None:
    report = analyze([0.05, 0.1, 0.2, 0.3, 0.4], ok=5, slo_latency_p95=0.5, slo_success=0.99)
    assert report["passed"] is True
    assert report["total"] == 5
    assert report["bad"] == 0
    assert report["success_rate"] == 1.0
    assert report["p95_seconds"] <= 0.5


def test_loadtest_analyze_fail_on_latency_and_success() -> None:
    report = analyze([1.0, 2.0, 3.0, 6.0, 9.0], ok=3, slo_latency_p95=5.0, slo_success=0.9)
    assert report["passed"] is False
    assert "latency" in report["failures"][0]
    # 成功率 60% < 90% -> 也失败
    report2 = analyze([0.1] * 5, ok=3, slo_latency_p95=5.0, slo_success=0.9)
    assert report2["passed"] is False
    assert any("success" in f for f in report2["failures"])


def test_loadtest_analyze_percentile() -> None:
    report = analyze([1, 2, 3, 4], ok=4, slo_latency_p95=10, slo_success=1.0)
    assert report["p50_seconds"] == 2.5
    assert round(report["p99_seconds"], 2) == 3.97  # 线性插值 0.99*3 -> 2.97


def test_release_gate_pass() -> None:
    slo = {
        "slos": [
            {"name": "api_availability", "budget": {"remaining_ratio": 0.9}},
            {"name": "task_success", "budget": {"remaining_ratio": 0.7}},
        ]
    }
    result = evaluate_gate({"status": "ok"}, "0.1.0", slo, "0.1.0", 0.5)
    assert result.passed is True
    assert len(result.checks) == 3


def test_release_gate_fail_on_version_and_budget() -> None:
    slo = {"slos": [{"name": "api_availability", "budget": {"remaining_ratio": 0.1}}]}
    result = evaluate_gate({"status": "ok"}, "0.1.0", slo, "0.2.0", 0.5)
    assert result.passed is False
    names = [c["name"] for c in result.checks]
    assert "version" in names and "error_budget" in names
    version_check = next(c for c in result.checks if c["name"] == "version")
    budget_check = next(c for c in result.checks if c["name"] == "error_budget")
    assert version_check["passed"] is False
    assert budget_check["passed"] is False  # 剩余 10% < 50% 门禁线


def test_metrics_endpoint_and_ops_slo() -> None:
    app = create_app()
    with TestClient(app) as client:
        resp = client.get("/metrics")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/plain")
        assert "flare_http_requests_total" in resp.text

        slo = client.get("/v1/ops/slo")
        assert slo.status_code == 200
        body = slo.json()
        assert body["overall"] in (SEV_NONE, SEV_WARNING, SEV_CRITICAL)
        names = [s["name"] for s in body["slos"]]
        assert names == ["api_availability", "task_success", "latency"]

        eb = client.get("/v1/ops/error-budget")
        assert eb.status_code == 200
        assert len(eb.json()["budgets"]) == 2
