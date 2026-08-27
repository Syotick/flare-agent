# 架构决策记录（ADR）

> 记录 Flare Agent 的关键架构决策：**背景 → 选项 → 决策 → 后果**。
> 原则：凡是影响方向、选型、协议、架构的决策，必须在此留痕；之后任何人（含新会话）都能追溯"为什么这么做"。

## 如何使用

1. 新建文件：`docs/adr/000N-简短标题.md`（编号递增，不重用）。
2. 用模板 [templates/adr-template.md](../templates/adr-template.md)。
3. 在 [docs/README.md](../README.md) 的 adr 索引登记。
4. 决策同时同步到 CLAUDE.md（项目记忆）。

## 状态字段

- `accepted` 已接受 / `proposed` 提议 / `superseded` 被取代（注明替代 ADR 编号）

## 已有 ADR

| 编号 | 标题 | 状态 | 日期 |
| --- | --- | --- | --- |
| 0001 | 数据库选型：PostgreSQL | accepted | 2026-08-27 |
| 0002 | 编排引擎：LangGraph | accepted | 2026-08-27 |
| 0003 | 运行时语言与 API 框架：Python + FastAPI | accepted | 2026-08-27 |
| 0004 | 向量库：Milvus（主选） | accepted | 2026-08-27 |
| 0005 | 会话与缓存：Redis | accepted | 2026-08-27 |
| 0006 | 消息队列：RocketMQ（生产）/ Kafka 备选 | accepted | 2026-08-27 |
| 0007 | 对象存储：阿里云 OSS / MinIO（本地） | accepted | 2026-08-27 |
| 0008 | 模型网关：自研 OpenAI 兼容（LiteLLM 起步） | accepted | 2026-08-27 |
| 0009 | 沙箱隔离：Kata/Firecracker 微虚拟化 | accepted | 2026-08-27 |
| 0010 | 推理服务：vLLM 首选 / SGLang 备选 | accepted | 2026-08-27 |
| 0011 | 可观测性：OpenTelemetry + Prometheus/Grafana + Loki | accepted | 2026-08-27 |
| 0012 | 前端形态：本地 Web 优先 | accepted | 2026-08-27 |
| 0013 | 部署平台：阿里云 ACK（K8s） | accepted | 2026-08-27 |
| 0014 | CI/CD：GitHub Actions | accepted | 2026-08-27 |
| 0015 | 工程结构：Monorepo + 模块化单体优先 | accepted | 2026-08-27 |
