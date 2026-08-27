# Flare Agent · M1 设计评审记录

> 版本：v1.0 ｜ 日期：2026-08-27 ｜ 状态：review
> 评审对象：02-module-design.md（模块级技术设计）+ 压测方案（docs/engineering/02-load-testing-plan.md）

---

## 1. 评审范围与依据

- 需求 v1.0（docs/product/requirements/01-development-requirements.md）
- 架构总览（01-architecture-overview.md）
- ADR-0001 ~ 0015（技术选型与结构决策）
- 工程规范（docs/engineering/01-development-standards.md）

## 2. 评审结论

**通过 ✅ —— 模块级设计与压测方案认可，进入 M2 开发。**
- 结构（Monorepo + 模块化单体优先）与需求/ADR 一致。
- 数据模型覆盖核心实体（任务/消息/工具/审批/知识库/审计/成本）。
- LangGraph 图包含预算熔断与人机审批，满足 FR-1/FR-7。

## 3. 主要设计决策（本次确认/新增）

| # | 决策 | 来源 |
| --- | --- | --- |
| 1 | 模块化单体起步，按需拆分 | ADR-0015 |
| 2 | OpenAI 兼容 API 作为统一对外协议 | ADR-0008 + 本设计 §4 |
| 3 | checkpoint 落 PG（LangGraph PostgresSaver） | ADR-0001 |
| 4 | 检索层抽象（Milvus/Qdrant/pgvector 可切换） | ADR-0004 |
| 5 | 本地环境 docker-compose 全组件化，不依赖云凭证 | ADR-0007/0013 |

## 4. 风险与未决问题

| 风险 | 等级 | 缓解 |
| --- | --- | --- |
| 模型供应商 API Key 尚未提供 | 中 | 先做 OpenAI 兼容接口 + mock 供应商实现，联调时切换 |
| 沙箱 Kata/Firecracker 本地不可用 | 中 | SandboxProvider 抽象，本地 Docker 降级，M5 接云 |
| 百万并发为设计目标，M2 不做全量验证 | 低 | M5 统一压测（方案已就绪） |
| 多租户权限模型待细化 | 中 | M2 实现最小租户上下文 + 中间件，RBAC 在 M5 强化 |

## 5. M2 开发范围（In/Out）

**In（M2 核心）**
- 仓库骨架：services/ 结构、common（配置/日志/OTel）、docker-compose
- agent-runtime：FastAPI + LangGraph 基础图（planner→actor→tool→reflect→finalize）+ checkpoint + 流式 SSE
- model-gateway：OpenAI 兼容 /v1/chat/completions + mock 供应商 + 语义缓存桩
- Web 壳：任务创建 + 实时流 + 结果展示（最小可用）
- CI：现有 pipeline 接通（lint/test 跑真实代码）+ 契约测试
- 单用户 E2E：Web 发起任务 → agent 调用工具 → 返回结果

**Out（后续里程碑）**
- RAG 全链路（M3）、多模型路由/配额（M4）、沙箱强隔离（M4）、多租户治理/压测（M5）

## 6. M1 DoD 验收

- [x] 模块级设计文档（目录/服务/API/数据模型/图/本地环境）
- [x] 压测方案（指标/工具/场景/容量模型/验收）
- [x] 技术选型定稿（ADR 0001-0015）
- [x] 需求 v1.0 已确认
- [x] 风险与未决项登记（§4）
- [ ] 用户确认本评审记录 → M2 开工
