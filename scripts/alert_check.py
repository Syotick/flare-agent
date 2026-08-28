"""告警检查（M6）：读取 /v1/ops/slo，按级别输出告警并决定退出码。

用法：
  python scripts/alert_check.py [--url http://127.0.0.1:8000]
  # 离线演练（无需真流量，给定快/慢窗口观测跑燃烧速率判定）：
  python scripts/alert_check.py --fast-bad 50 --fast-total 1000 --slow-bad 200 --slow-total 10000

- 无窗口参数：读取服务端 /v1/ops/slo 的实时分级（HTTP/任务/延迟三个 SLO）；
- 有窗口参数：用本机给定的快/慢窗口观测跑一遍多窗口燃烧速率判定（离线演练告警逻辑，
  不需真流量），输出 P0/P1/P2。
- 退出码：0=无告警或仅 P2；1=存在 P0/P1（阻断发布/下班）。
"""

from __future__ import annotations

import argparse
import sys

import httpx

from flare_common.slo import SLO, Alert, Observation, classify_multi, highest_severity


def _print_alerts(alerts: list[Alert]) -> None:
    print("=== 告警检查 ===")
    for a in alerts:
        mark = {"critical": "P0", "warning": "P2", "none": "-"}[a.severity]
        print(f"  [{mark}] {a.name}: {a.message}")
    print("结论:", highest_severity(alerts) or "正常")


def _offline(args) -> int:
    """离线多窗口燃烧速率演练（-1=该窗口未提供，按 0 计）。"""
    slo = SLO("offline_availability", 0.99)
    fast = Observation(total=args.fast_total, bad=max(args.fast_bad, 0), window_seconds=300)
    slow = Observation(total=args.slow_total, bad=max(args.slow_bad, 0), window_seconds=3600)
    alert = classify_multi(slo, fast, slow)
    _print_alerts([alert])
    return 1 if alert.severity in ("critical", "warning") else 0


def _live(args) -> int:
    resp = httpx.get(args.url + "/v1/ops/slo", timeout=10)
    resp.raise_for_status()
    body = resp.json()
    alerts = [
        Alert(severity=s["alert"]["severity"], name=s["name"], message=s["alert"]["message"])
        for s in body["slos"]
    ]
    _print_alerts(alerts)
    return 1 if highest_severity(alerts) == "critical" else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Flare Agent 告警检查")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--fast-bad", type=int, default=-1)
    parser.add_argument("--fast-total", type=int, default=1000)
    parser.add_argument("--slow-bad", type=int, default=-1)
    parser.add_argument("--slow-total", type=int, default=10000)
    args = parser.parse_args()
    if args.fast_bad >= 0 or args.slow_bad >= 0:
        return _offline(args)
    return _live(args)


if __name__ == "__main__":
    sys.exit(main())
