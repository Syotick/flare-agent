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
- 侧栏工作区导航：对话 / 知识库 / 记忆 / 运维，视图切换；api.ts 统一后端 REST/SSE 客户端
- 运维中心页（OpsView，M6 配套）：SLO 三卡片（可用性/任务成功率/延迟 p95，目标+错误预算进度条+告警分级徽章）、整体状态横幅、Prometheus /metrics 原始指标折叠查看、15s 自动刷新

### Added（MCP 客户端 + Skills，FR-2/FR-3，2026-08-28）
- MCP 客户端（services/mcp）：JSON-RPC 2.0 协议层（零依赖）+ McpClient（initialize 握手 / tools/list / tools/call）+ 双传输（Streamable HTTP / HTTP+SSE，httpx）；协议层与传输层分离，传输可插拔
- MCP 工具适配：外部工具 → ToolRegistry.Tool（命名空间 mcp__<server>__<tool>，inputSchema 复用统一校验层），Agent 原生 function-calling 直接调用
- MCP 网关（McpGateway，FR-2.3）：多服务器统一管理、服务器级/工具级白名单、认证头注入、审计钩子、幂等注册；配置 FLARE_MCP_SERVERS（JSON）
- MCP 内置工具：mcp_connect（按需连接+注册）/ mcp_list（连接状态与已注册工具）
- 测试基建（mcp/testing.py）：FakeTransport（进程内）+ MemoryMcpServer（stdlib 真实 HTTP，支持 Streamable 与 SSE 双形态，零依赖）
- Skills 机制（services/skills）：SKILL.md 声明式技能包（frontmatter 零依赖 YAML 子集解析 + 指令 + resources/ + required_tools）、SkillRegistry（安装/卸载/列表/build_context 上下文注入）、skill_list / skill_load 工具
- 示例技能 examples/skills/code-review；演示脚本 scripts/demo_mcp.py + scripts/demo_skills.py
- 测试：新增 22 个（test_mcp 13 + test_skills 9），全量 142 全绿，ruff/black 干净
- 文档：learning/13-mcp-and-skills.md；功能盘点与竞品对比 docs/product/analysis/01-competitive-comparison.md（登记 docs/README）
- 修复部署阻断：pyproject packages.find 补 mcp*/skills*（否则生产的 wheel 缺这两个包，同 memory* 坑）

### Changed
- Composer 移除对用户暴露的工程参数（max_steps / thread_id）：内部常量 MAX_STEPS=8，线程由系统全自动管理

### Fixed
- 会话切换：切换时先清空消息区再 SSE 回放（防旧会话残留/叠加），并沿用该会话线程续聊
- 新会话第 2 条消息开新线程的上下文断裂：send 成功后同步服务端生成的 thread_id
- 刷新（hash 恢复）后不续线程：恢复时沿用会话的 thread_id

### Added（M6 生产运营）
- 可观测性：纯 Python 指标注册表（flare_common/metrics.py，Counter/Histogram + Prometheus 文本格式）、HTTP 指标中间件、任务结果埋点、/metrics 端点（零外部依赖）
- SLO/错误预算：flare_common/slo.py（SLO 目标/错误预算/燃烧速率/多窗口告警分级），环境变量 FLARE_SLO_* 可调
- 运维 API：/v1/ops/slo（三个 SLO 状态 + 分级）、/v1/ops/error-budget
- 告警基建：infra/k8s/08-prometheus-rules.yaml（燃烧速率/延迟/5xx 告警）、09-alertmanager.yaml（P0→page/P2→slack 路由）、10-service-monitor.yaml（采集 /metrics）
- 压测：scripts/loadtest.py（进程内 mock 可跑 / 对线上 URL 打流量，p50/p95/p99+成功率 vs SLO，报告落 data/loadtest_report.json，未达标退出码 1）
- 发布门禁：scripts/release_gate.py（健康+版本+错误预算，放行/阻断）+ 回滚演练 runbook（learning/12 §7）
- 告警检查：scripts/alert_check.py（在线读 /v1/ops/slo + 离线多窗口燃烧速率演练）

### Docs
- 教学文档 learning/01–12（面试题库/RAG 入库/分层记忆/进阶开发/生产部署/四视图架构/RAG 评测/模型网关与沙箱/Web 控制台与产品化 UX/生产运营 SRE）
- 架构决策 ADR 0001–0015；工程规范与三轮代码审查记录；Web Console 功能清单
