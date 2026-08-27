# AGENTS.md — Flare Agent 项目记忆（标准版）

> 与 CLAUDE.md 同源，供所有支持 AGENTS.md 的 Agent 工具读取。
> 变更时两处同步。

## 项目目标
企业级 AI Agent 平台，对标 Codex / Claude Code / DeepSeek Harness，
可上线、高可用、可拓展、可运维，估算并发百万级，部署阿里云，对象存储用阿里云 OSS，
集成 RAG / MCP / Skills / 工具系统 / 沙箱 / 记忆等先进能力。非 demo。

## 关键约束
0. **推送策略（用户 2026-08-27 明确）**：默认只本地 git commit，不主动 push 远程；只有用户明确要求时才推送/发 PR。
1. **Python 环境**：conda env `flare-agent`（Python 3.12），不用 .venv；命令 `conda run -n flare-agent python` 或 `make test/lint/dev`。
1. 生产级（可部署、可监控、可回滚、可审计）
2. 高可用（多可用区、无单点）
3. 弹性扩展到百万级并发
4. 组件化可插拔（Tools / MCP / Skills / RAG）
5. 多模型可路由
6. 阿里云 OSS 存对象
7. 强企业级技术栈，云原生

## 已确认决策（2026-08-27）
- 技术栈：Python + LangGraph + FastAPI + Milvus（主选）+ 自研 OpenAI 兼容模型网关（可自托管 vLLM/SGLang）
- 产品形态：本地 Web 优先（预留 CLI/API）
- 沙箱：微虚拟化强隔离（Kata/Firecracker），本地开发 Docker 降级
- 阿里云凭证：后续提供，开发阶段用本地模拟（MinIO 模拟 OSS、本地 Redis/PG/向量库），存储层 Provider 可切换
- 新增需求：面试题驱动开发——全面覆盖高级 Agent 工程师考点（多路召回/GraphRAG/记忆/安全/高并发等），实践+真理并重

## 当前进度
- 阶段 0/1 完成：Git 仓库（已公开 Syotick/flare-agent）+ 文档体系 + 记忆 + M1 设计评审（ADR ×15、模块设计、压测方案）
- **M2 核心闭环完成**：flare_common / agent_runtime(ReAct 图+任务 API：POST 202+SSE 真流式+GET 详情/列表+DELETE 删除) / tools_gateway / model_gateway / **web Console(Vite+React18+Tailwind v4+shadcn(Radix)+lucide，flare 耀斑主题，参考 nova-agent)**；conda env flare-agent；make web-dev / web-build
- **M3a RAG 知识库完成**：services/rag 分层（chunking→embedder→store→pipeline 门面），开发默认 HashEmbedder+SqliteVectorStore（生产换 DashScopeEmbedder+pgvector，协议可插拔）；kb_search 工具注入 Agent 注册表；/v1/kb/documents(POST/GET/DELETE)+/v1/kb/search；TestClient 必须用 with 块（否则后台任务被临时 loop 丢弃）；pytest 42 全绿，ruff/black 干净
- 代码审查：R1=engineering/03；R2=engineering/04（F1-F4）；R3=engineering/05（Web 前端 L1-L4+问题2/3）
- 下一步：M3 RAG 知识库 + 记忆体系（或先做单用户 E2E 验收）

## 目录速览
- `docs/README.md` — 文档中心（总索引 + 管理规范，**唯一入口**）
- `docs/product/` — 产品与技术参考（调研/需求/架构）
- `docs/engineering/` — 开发与工程规范（开发文档）
- `docs/learning/` — 学习与面试（面试题库）
- `docs/adr/` — 架构决策记录
- `CLAUDE.md` — 详细项目记忆（唯一权威源）

## 待决策
预算/模型供应商（开发先默认 DeepSeek/通义兼容接口 + 多供应商可配）、运维人力。
