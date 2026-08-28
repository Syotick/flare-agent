# Flare Agent · 生产运营（SLO / 告警 / 压测 / 扩缩容 / 回滚演练）——实践 + 真理

> 版本：v1.0 ｜ 日期：2026-08-28 ｜ 状态：draft
> 定位：M6 配套教学文档——系统上线后怎么"活下来"：SLO 怎么定、错误预算怎么算、
> 告警怎么分级、本地怎么压测、容量怎么估、上线怎么放行、出问题怎么回滚。
> 配套：05-生产部署指南（部署部分）、engineering/02-压测方案、ADR-0011（可观测性）。

---

## 1. 可运维可上线的第一性真理

- 真理：**没有 SLO 的系统等于没有质量承诺**——"很稳"不可度量，SLO 才是能签的契约。
  SLO 不是"想达到的"而是"用户可接受的底线"，超过 SLO 的钱（错误预算）用于放心地发版。
- 真理：**错误预算让"发版风险"可量化**：预算=100%×(1−SLO)。
  用完预算就冻结发版（回滚优先），剩余预算就是"这次可以冒险的额度"。
- 真理：**告警要按燃烧速率，不要按绝对值**——"5xx 20 次"没意义，
  "5 分钟烧掉 2.5% 的 30 天预算"才有行动价值（多窗口燃烧速率）。
- 真理：本地与生产共用同一套判定逻辑（纯函数），
  压测/告警演练在本地 mock 就能跑——逻辑先本地验明，真金不怕火炼。

## 2. SLO 定义与错误预算（services/flare_common/slo.py）

- 本项目三个 SLO（FLARE_SLO_* 环境变量可调，默认 30 天周期）：
  1. **api_availability**：HTTP 非 4xx/5xx 率 >= 99%（4xx 是客户端错，不算我方故障）；
  2. **task_success**：Agent 任务成功率 >= 99%（completed 才算成功）；
  3. **latency**：HTTP p95 延迟 <= 5s。
- 错误预算数学（error_budget）：
  - 预算 = total × (1 − target)；例：1000 请求、99% SLO → 允许 10 个失败；
  - consumed = bad / 预算；remaining = max(1 − consumed, 0)。
- 燃烧速率（burn_rate）：窗口内消耗预算比例 / (窗口时长 / 周期)。
  - 1x = 正好在周期末耗尽预算；36x = 预算约 20 小时内烧光，必须立刻处理。
- 生产配置（12-factor）：FLARE_SLO_AVAILABILITY=0.99、FLARE_SLO_P95_LATENCY_SECONDS=5.0、FLARE_SLO_PERIOD_DAYS=30。

## 3. 告警分级与 Runbook（P0 / P1 / P2）

- 分级（severity 稳定，前端/通知按此路由）：
  | 级别 | 触发（默认阈值，可调） | 行动 |
  | --- | --- | --- |
  | P0 critical | 快窗口(5m) burn>=36x 或慢窗口(1h) burn>=36x，或 p95 超 SLO 持续 10m | 立即处理，冻结发版 |
  | P2 warning | 慢窗口(1h) burn>=14.4x，或 5xx 比例>5% 持续 10m | 当日处理，Slack/工单 |
  | none | 燃烧速率正常 | 无动作 |
- 判定代码：slo.py 的 classify_burn / classify_multi（纯函数，已被单测覆盖）。
- 离线演练（不产生真流量就能验告警逻辑）：
  python scripts/alert_check.py --fast-bad 50 --fast-total 1000 --slow-bad 200 --slow-total 10000
- 生产告警规则：infra/k8s/08-prometheus-rules.yaml（PrometheusRule）；
  通知路由：infra/k8s/09-alertmanager.yaml（P0->page/email，P2->slack）。
- Runbook 速查（出 P0 怎么办）：
  1. 看 /v1/ops/slo 与 /metrics，确认哪个 SLO、哪个窗口在烧；
  2. 看 5xx 分布（by_status）定位是网关/后端/模型哪个环节；
  3. 模型供应商抖动 -> 切 mock/备用供应商，重试已在网关层（M4）；
  4. 容量问题 -> 扩 HPA 副本/加缓存；代码问题 -> 按 §7 回滚；
  5. 处理完看错误预算：烧掉的记在账上，决定是否冻结发版。

## 4. 可观测性（/metrics + OTel）

- 纯 Python 指标注册表（flare_common/metrics.py）：Counter/Histogram + Prometheus 文本格式，
  /metrics 端点输出（text/plain; version=0.0.4），生产由 ServiceMonitor 采集（10-service-monitor.yaml）。
- 已埋点：HTTP 请求数(按方法/路径/状态)、HTTP 耗时直方图、任务结果计数、任务端到端耗时。
- 指标名统一 flare_* 前缀；命名符合 Prometheus 惯例（_total/_seconds/_bucket/_sum/_count）。
- OTel tracing（M5）：FLARE_OTEL_ENDPOINT 为空时 no-op，生产指向 Collector 导出 traces。
- 关键指标（告警规则用到）：
  - flare_http_requests_total{status="5xx"} 比例（可用性）
  - histogram_quantile(0.95, rate(flare_http_request_duration_seconds_bucket[5m]))（延迟）
  - flare_task_runs_total{outcome="errored"}（任务成功率）

## 5. 本地压测与容量模型（scripts/loadtest.py）

- 进程内压测（不依赖服务、不占 sqlite 锁，mock 模型）：
  python scripts/loadtest.py --concurrency 8 --iterations 20
- 对已运行服务打流量（更贴近生产）：
  python scripts/loadtest.py --url http://127.0.0.1:8000 --concurrency 16 --iterations 50
- 输出：p50/p95/p99、吞吐（qps）、成功率，与 SLO 对比出 PASS/FAIL，报告落 data/loadtest_report.json；
  任一 SLO 未达标退出码 1（可接 CI 门禁）。
- 容量模型：单实例吞吐 × 副本数 >= 目标峰值；HPA 按 CPU 70% 在 2~10 副本间伸缩；
  百万并发是"服务端可水平扩展"的目标——先本地压出单实例上限，再用副本数乘出来，
  生产以实测为准，绝不拍脑袋。

## 6. 扩缩容（HPA 已在 M5 就绪，05-hpa.yaml）

- CPU 70% 触发扩容，min=2 max=10；生产再叠加 qps 自定义指标（ServiceMonitor 已采集）。
- 扩缩容纪律：扩容是容量问题的短期解，长期靠缓存/异步/限流；HPA 抖动就加冷却。

## 7. 发布门禁与回滚演练（scripts/release_gate.py + kubectl）

- 门禁：上线/回滚前后跑一次，健康+版本+错误预算全部达标才放行：
  python scripts/release_gate.py --url http://127.0.0.1:8000 --expected-version 0.1.0
- 回滚演练（生产）：
  1. 确认问题版本镜像（如 flare-agent:bad-1.0）；
  2. 执行回滚：kubectl rollout undo deployment/flare-agent -n flare-agent
     （或 helm rollback flare-agent 上一版）；
  3. 等 rollout 完成：kubectl rollout status deployment/flare-agent -n flare-agent;
  4. 跑发布门禁确认健康/版本/预算；
  5. 演练记录：从发现到恢复的时长、是否触发告警、错误预算烧了多少——写进值班交接。
- 真理：回滚不是"失败"，是发布流程的正常分支；**可回滚性（快速、可验证）比一次发布正确更值钱**。

## 8. 踩坑经验（M6 实测）

- **dev SQLite checkpointer 长连接会锁文件**：运行中的服务持有 data/flare_agent.sqlite3 连接，
  第二个本地进程（冒烟/压测）再去初始化会一直卡住（像挂死）。
  对策：本地脚本注入 MemorySaver（loadtest 已内置）；别跟运行中服务抢同一个 sqlite。
- **prometheus_client 不是硬依赖**：纯 Python 实现即可满足 Prometheus 文本格式，生产可平滑换官方库。
- **heredoc 写长文档会被工具截断**：分段（每段 < 30 行）写并核对行数。
- **燃烧速率阈值别拍脑袋**：默认 14.4x/36x 是 Google SRE 多窗口标准值，先按标准跑再按业务调。

## 9. 一页速记（面试/自检）

1. SLO 是可签的质量契约；错误预算 = 100% × (1 − SLO)，用预算决定敢不敢发版。
2. 告警按燃烧速率分级：P0 = 快/慢窗口高速烧穿（36x），P2 = 慢窗口 14.4x。
3. 可观测性三件套：/metrics（Prometheus 文本）+ OTel traces + 结构化错误码。
4. 压测先本地（mock + MemorySaver）验逻辑，生产以实测容量为准，HPA 是短期解。
5. 发布门禁（健康+版本+预算）把关上线与回滚；可回滚性比一次发布正确更值钱。

