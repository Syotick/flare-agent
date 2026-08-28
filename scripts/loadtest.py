"""本地压测（M6）：打真实流量 → SLO 对比报告，可做容量/回归门禁。

用法：
  python scripts/loadtest.py --concurrency 8 --iterations 20
  python scripts/loadtest.py --url http://127.0.0.1:8000 --concurrency 16 --iterations 50
  python scripts/loadtest.py --concurrency 8 --iterations 20 --latency-p95 5.0 --success 0.99

- 无 --url：在进程内以 ASGI 跑 app（注入 MemorySaver，避免与运行中的服务争用
  data/flare_agent.sqlite3 锁——dev SQLite checkpointer 长连接会锁文件，多进程会挂起）；
- 有 --url：对已运行服务打流量（更贴近生产路径）。
- 输出：控制台报告 + data/loadtest_report.json；任一 SLO 未达标退出码 1（可接 CI 门禁）。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

import httpx

TERMINAL = ("completed", "budget_exceeded", "failed")


def percentile(sorted_values: list[float], q: float) -> float:
    """线性插值分位数（q∈[0,1]）。"""
    if not sorted_values:
        return 0.0
    if q <= 0:
        return sorted_values[0]
    if q >= 1:
        return sorted_values[-1]
    pos = q * (len(sorted_values) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_values) - 1)
    frac = pos - lo
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * frac


def analyze(
    timings: list[float],
    ok: int,
    slo_latency_p95: float = 5.0,
    slo_success: float = 0.99,
) -> dict:
    """把压测结果折算成 SLO 报告（纯函数，可测）。timings 单位秒。"""
    total = len(timings)
    bad = total - ok
    sorted_t = sorted(timings)
    p50 = percentile(sorted_t, 0.5)
    p95 = percentile(sorted_t, 0.95)
    p99 = percentile(sorted_t, 0.99)
    avg = statistics.mean(timings) if timings else 0.0
    success_rate = ok / total if total else 1.0
    latency_pass = p95 <= slo_latency_p95
    success_pass = success_rate >= slo_success
    passed = latency_pass and success_pass
    return {
        "total": total,
        "ok": ok,
        "bad": bad,
        "p50_seconds": round(p50, 4),
        "p95_seconds": round(p95, 4),
        "p99_seconds": round(p99, 4),
        "avg_seconds": round(avg, 4),
        "success_rate": round(success_rate, 4),
        "throughput_qps": round(total / max(sum(timings), 1e-9), 3),
        "slo": {"latency_p95_seconds": slo_latency_p95, "success": slo_success},
        "passed": passed,
        "failures": [
            *(["latency: p95 超出目标"] if not latency_pass else []),
            *(["success: 成功率低于目标"] if not success_pass else []),
        ],
    }


def _in_process_app():
    """进程内 ASGI app：mock 模型 + MemorySaver（不碰共享 sqlite 锁）。"""
    from langgraph.checkpoint.memory import MemorySaver

    from agent_runtime.app import create_app
    from agent_runtime.tasks import TaskManager
    from model_gateway.mock import MockModelProvider
    from tools_gateway.builtin import create_default_registry

    async def _mem():
        return MemorySaver()

    return create_app(
        task_manager=TaskManager(
            registry=create_default_registry(),
            llm=MockModelProvider(),
            checkpointer_factory=_mem,
        )
    )


async def _run_one(client: httpx.AsyncClient, idx: int) -> tuple[float, bool]:
    """执行一次端到端任务：POST 建任务 → 轮询到终态，返回 (耗时秒, 是否成功)。"""
    task_input = f"计算 {idx % 90 + 10}+{idx % 90 + 1}=?（压测 #{idx}）"
    started = time.perf_counter()
    created = await client.post("/v1/tasks", json={"task_input": task_input, "max_steps": 2})
    if created.status_code != 202:
        return time.perf_counter() - started, False
    task_id = created.json()["task_id"]
    deadline = time.perf_counter() + 30
    status = "pending"
    while time.perf_counter() < deadline:
        body = await client.get(f"/v1/tasks/{task_id}")
        status = body.json().get("status", "pending")
        if status in TERMINAL:
            break
        await asyncio.sleep(0.02)
    ok = status == "completed"
    return time.perf_counter() - started, ok


async def _run_loadtest(args) -> dict:
    if args.url:
        transport = None
        base = args.url
    else:
        app = _in_process_app()
        transport = httpx.ASGITransport(app=app)
        base = "http://localhost"

    async with httpx.AsyncClient(transport=transport, base_url=base, timeout=60) as client:
        sem = asyncio.Semaphore(args.concurrency)
        timings: list[float] = []
        ok_count = 0

        async def worker(i: int) -> None:
            nonlocal ok_count
            async with sem:
                try:
                    duration, ok = await _run_one(client, i)
                except httpx.HTTPError as exc:  # 网络/超时都算失败
                    duration, ok = 0.0, False
                    print(f"[warn] iteration {i} 失败: {exc}")
                timings.append(duration)
                if ok:
                    ok_count += 1

        started = time.perf_counter()
        await asyncio.gather(*(worker(i) for i in range(args.iterations)))
        wall = time.perf_counter() - started
        report = analyze(timings, ok_count, args.latency_p95, args.success)
        report["wall_seconds"] = round(wall, 2)
        report["concurrency"] = args.concurrency
        report["throughput_qps_wall"] = round(args.iterations / wall, 3)
        return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Flare Agent 本地压测（SLO 对比）")
    parser.add_argument("--concurrency", type=int, default=8, help="并发数（默认 8）")
    parser.add_argument("--iterations", type=int, default=20, help="总迭代次数（默认 20）")
    parser.add_argument("--url", default="", help="目标服务 URL；缺省=进程内 ASGI")
    parser.add_argument("--latency-p95", type=float, default=5.0, help="p95 延迟 SLO（秒）")
    parser.add_argument("--success", type=float, default=0.99, help="成功率 SLO（0~1）")
    parser.add_argument("--report", default="data/loadtest_report.json", help="报告输出路径")
    args = parser.parse_args()

    report = asyncio.run(_run_loadtest(args))
    out = Path(args.report)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=== 压测报告 ===")
    print(
        f"  迭代 {report['total']}（并发 {report['concurrency']}）  墙钟 {report['wall_seconds']}s"
    )
    thr = (
        f"{report['throughput_qps_wall']} qps（含排队） / {report['throughput_qps']} qps（纯处理）"
    )
    print(f"  吞吐 {thr}")
    lat = (
        f"p50={report['p50_seconds']}s  p95={report['p95_seconds']}s  p99={report['p99_seconds']}s"
    )
    print(f"  {lat}")
    print(f"  成功率 {report['success_rate'] * 100:.2f}%  失败 {report['bad']}")
    target = (
        f"p95<={report['slo']['latency_p95_seconds']}s, "
        f"成功率>={report['slo']['success'] * 100:.0f}%"
    )
    print(f"  SLO 目标: {target}")
    print(f"  结论: {'PASS' if report['passed'] else 'FAIL'} {'; '.join(report['failures'])}")
    print(f"  报告: {out}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
