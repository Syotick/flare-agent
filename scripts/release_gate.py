"""发布门禁（M6）：上线/回滚前后校验——健康、版本、错误预算，任一不达标即阻断。

用法：
  python scripts/release_gate.py --url http://127.0.0.1:8000
  python scripts/release_gate.py --url http://127.0.0.1:8000 \
    --expected-version 0.1.0 --max-budget-ratio 0.5

纯函数 evaluate_gate 可单测；CLI 只是把 HTTP 结果喂给它。
退出码：0=放行，1=阻断。
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass
class GateResult:
    passed: bool
    checks: list[dict[str, Any]] = field(default_factory=list)

    def add(self, name: str, ok: bool, detail: str) -> None:
        self.checks.append({"name": name, "passed": ok, "detail": detail})


def evaluate_gate(
    health: dict | None,
    version: str | None,
    slo: dict | None,
    expected_version: str | None = None,
    max_budget_ratio: float = 0.5,
) -> GateResult:
    """纯函数门禁判定。所有入参为 None 表示该检查不可用。"""
    result = GateResult(True)
    result.add("health", health is not None and health.get("status") == "ok", str(health))
    if expected_version:
        result.add(
            "version",
            version == expected_version,
            f"期望 {expected_version}，实际 {version!r}",
        )
    budgets_ok = True
    details: list[str] = []
    if slo:
        for s in slo.get("slos", []):
            budget = s.get("budget")
            if budget is None:
                continue
            remaining = budget.get("remaining_ratio", 0.0)
            ok = remaining >= (1.0 - max_budget_ratio)
            budgets_ok = budgets_ok and ok
            details.append(f"{s['name']}: 预算剩余 {remaining * 100:.1f}%")
    result.add("error_budget", budgets_ok, "; ".join(details) or "无预算数据")
    result.passed = all(c["passed"] for c in result.checks)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Flare Agent 发布门禁")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--expected-version", default="")
    parser.add_argument("--max-budget-ratio", type=float, default=0.5)
    args = parser.parse_args()

    with httpx.Client(base_url=args.url, timeout=10) as client:
        health = client.get("/health").json() if client.get("/health").status_code == 200 else None
        ver = (
            client.get("/version").json().get("version")
            if client.get("/version").status_code == 200
            else None
        )
        slo_resp = client.get("/v1/ops/slo")
        slo = slo_resp.json() if slo_resp.status_code == 200 else None

    result = evaluate_gate(health, ver, slo, args.expected_version or None, args.max_budget_ratio)
    for c in result.checks:
        print(f"  [{'PASS' if c['passed'] else 'FAIL'}] {c['name']}: {c['detail']}")
    print("结论:", "放行" if result.passed else "阻断")
    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
