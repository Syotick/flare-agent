# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 与 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### Added
- 项目初始化：文档骨架（调研/需求/架构/工程规范）、项目记忆（CLAUDE.md / AGENTS.md）
- 高级 Agent 工程师面试题库（实践 + 真理）
- 仓库工程化配置：CI/CD 工作流、Issue/PR 模板、安全策略、行为准则、贡献指南

### Added（核心运行时）
- ReAct 推理循环（LangGraph 编排，graph.actor 单轮 think→decide→act），mock 模型零依赖可跑
- 工具系统：工具注册中心 + 内置工具（时间/计算/HTTP/沙箱/知识库检索/记忆读写），结构化 ToolResult
- RAG 知识库（M3a）：入库管线（分块 + 向量化 + SQLite/PG 向量存储）、hybrid 混合检索（BM25+向量 RRF）、重排
- 分层记忆（M3b）：长期事实（KV）+ 向量记忆（note）+ 会话上下文块（F4.3 上下文工程）
- RAG 评测（M3c）：确定性指标（recall/MRR/NDCG）+ 数据集 + RAGAS 式 LLM 判定（proxy/llm），诚实报告 skipped
- 模型网关（M4）：OpenAI 兼容供应商抽象 + function-calling 映射 + 指数退避重试，mock/openai 可切换
- 沙箱（M4）：LocalProcessSandbox（超时/输出上限/内存上限）+ DockerSandbox 占位（不可用 fail-fast），sandbox_run 工具
- 多租户（M5）：X-Tenant-Id → contextvar 透传，租户隔离的任务/记忆/知识库
- 任务存储（M5）：TaskStore 抽象（InMemory / SQLite / Redis），异步 checkpoint（MemorySaver / AsyncPostgresSaver）
- 可观测性（M5）：OpenTelemetry 初始化（无 endpoint 时 no-op），健康/版本探针
- 生产就绪基建（M5）：infra/Dockerfile + K8s 7 清单（Deployment/Service/ConfigMap/Secret/HPA/PDB/Ingress）、双写对账脚本 scripts/reconcile.py
- 测试：103 个单测全绿（asyncio_mode=auto），ruff + black 全量干净

### Added（Web 控制台）
- 对话工作区：SSE 实时流式对话 + 工具调用轨迹卡片（ThinkingOrb / ToolCallCard / WelcomePanel）
- 知识库管理页（KnowledgeBaseView）：入库、文档列表/删除、hybrid 检索、RAG 评测可视化
- 记忆管理页（MemoryView）：事实 CRUD、向量记忆检索、上下文块预览
- 侧栏工作区导航：对话 / 知识库 / 记忆，视图切换；api.ts 统一后端 REST/SSE 客户端

### Changed
- Composer 移除对用户暴露的工程参数（max_steps / thread_id）：内部常量 MAX_STEPS=8，线程由系统全自动管理

### Fixed
- 会话切换：切换时先清空消息区再 SSE 回放（防旧会话残留/叠加），并沿用该会话线程续聊
- 新会话第 2 条消息开新线程的上下文断裂：send 成功后同步服务端生成的 thread_id
- 刷新（hash 恢复）后不续线程：恢复时沿用会话的 thread_id

### Docs
- 教学文档 learning/01–11（面试题库/RAG 入库/分层记忆/进阶开发/生产部署/四视图架构/RAG 评测/模型网关与沙箱/Web 控制台与产品化 UX）
- 架构决策 ADR 0001–0015；工程规范与三轮代码审查记录；Web Console 功能清单
