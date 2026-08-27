# ADR-0011 · 可观测性：OpenTelemetry + Prometheus/Grafana + Loki

> 状态：accepted
> 日期：2026-08-27
> 决策人：Syotick（用户确认）
> 关联：docs/product/research/01-market-and-tech-research.md §10

## 背景（Context）

LLMOps 需要全链路追踪/指标/日志，遵循 GenAI 语义约定（token/工具/检索/成本）；"一条任务一条 trace"便于调试。

## 备选方案（Options）

| 方案 | 优点 | 缺点 |
| --- | --- | --- |
| OTel + 开源栈 | 统一标准、不锁定、GenAI 语义约定 | 自建组件运维 |
| 商业（NewRelic/Datadog） | 开箱即用 | 成本高、数据出境 |
| 阿里云 ARMS + SLS | 托管、生态 | 绑定云厂商 |

## 决策（Decision）

- 选择：**OpenTelemetry 埋点 + Prometheus/Grafana 指标 + Loki/阿里云 SLS 日志；Langfuse 可选**
- 理由：标准化 + 可迁移；满足全链路追踪需求。

## 后果（Consequences）

- 正面：统一观测、可复现、成本可审计。
- 代价：自建组件需维护（托管降级）。
- 迁移/回滚：OTel 标准使后端可切换。
