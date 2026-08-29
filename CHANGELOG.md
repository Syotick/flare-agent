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

### Added（多 Agent / Subagent 并行，F1.4，2026-08-28）
- SubagentRuntime（services/subagent）：子任务 = 独立 ReAct Agent 实例（复用 build_react_agent + MemorySaver 临时 checkpointer），进程内 asyncio 后台任务并发执行；独立预算（max_steps）/独立超时（timed_out）/存活上限 MAX_ACTIVE=64 护栏；spawn / await（shield 超时不打断底层）/ run_subagents（asyncio.gather 并行收集）/ list / close
- 编排工具：spawn_subagent / await_subagent / list_subagents / run_subagents（并行核心原语，单次上限 16 个 prompt）——父 Agent 拆解任务 → 并行执行 → 自行汇总；失败转结构化 ToolResult
- 接线：create_app 注入 SubagentRuntime（共享父 llm/registry），TaskManager 暴露 llm/registry 属性
- 演示脚本 scripts/demo_subagent.py；教学文档 learning/14-multi-agent.md（已登记 docs/README）
- 测试：新增 9 个（test_subagent，含 max_active>=2 证明真并发 + 超时护栏），全量 152 全绿，ruff/black 干净

### Added（前端入口闭环 + 能力盘点 API，2026-08-28）
- 死代码治理：MCP/Skills/多 Agent/OpenAI 兼容 API 此前只以 agent 工具存在（控制台无入口）——补 /v1/capabilities/* 只读路由（routes/capabilities.py）：tools（工具注册表 JSON-Schema）/ skills + skills/{name}（指令+资源全文）/ mcp（gateway.status() 快照）/ subagent（active_count + 子任务记录）；可选依赖未装配返回空态
- 前端能力中心（CapabilitiesView.tsx 四页签：工具/技能/MCP/多 Agent）+ 开发者入口（ApiView.tsx：OpenAI 兼容 Playground + /v1/models + curl/CLI/SDK 接入示例）；侧栏死占位项"技能·轨迹·工具"修复为可点「能力」，新增「开发者」
- app.py 挂载（skill_registry 提升到 create_app 作用域）；api.ts 统一层新增客户端；tsc(strict)+vite build 通过
- 测试：test_capabilities 6 例（工具/技能详情+404/未装配空态/MCP 快照/subagent 记录/create_app 挂载冒烟），全量 178 全绿；真实服务器冒烟：13 工具清单 + skills + subagent + models + chat.completions 全部打通
- learning/11 补 §10「前端入口闭环」（治理原则：一个能力 = 一个 REST 端点 + 一个前端视图）

### Added（CLI + OpenAI 兼容 REST API，F9.2/F9.3，2026-08-28）
- OpenAI 兼容端点（routes/openai_compat.py）：POST /v1/chat/completions（标准 Chat Completions 契约，含 stream=true SSE 分块 + [DONE]）+ GET /v1/models；复用 TaskManager（任务登记/可观测/可查同一套存储），非流式内部轮询等待（同步语义的异步执行）
- OpenAI 兼容错误：扁平 {"error":{message,type,param,code}}（自定义 OpenAICompatError → JSONResponse，不经 FastAPI detail 包装）；可选认证 FLARE_API_KEY（Bearer，空=开放）
- CLI（services/flare_cli）：flare chat（流式/--json）/ tasks / task(--stream) / models；httpx 瘦客户端 FlareClient 可注入 ASGITransport 测试；pyproject [project.scripts] flare + 包 flare_cli*
- 接线：app.py 挂载 openai 路由（api_key=settings.api_key）；Settings 加 api_key；.env.example 补 FLARE_API_KEY/FLARE_URL
- 教学文档 learning/15（已登记 docs/README）；测试新增 12（test_openai_compat 6 + test_flare_cli 5 + 复用），全量 172 全绿
- 冒烟验证：真实 uvicorn + python -m flare_cli（models/chat 流式/tasks/--json）端到端打通

### Fixed（Round 6 审查，2026-08-28）
- M1 图内工具 schema 冻结：graph.actor 每轮用当前 registry 重建 system 工具清单（原位替换）——mcp_connect 中途注册的新工具同任务内对模型可见可调；补 ReAct 图端到端用例
- M2 SSE 跨 chunk 拆分：新增 _split_sse_events 增量切分（只消费空行结尾的完整事件，残余保留 buffer）；testing.py 支持 sse_chunk 分块写出 + sse_response_delay
- M3 MCP 超时可配置：McpServerConfig.timeout → _make_client → build_transport 透传（此前 McpClient._timeout 实际未达传输层）；202 显式 Content-Length:0
- M4 register_all(server_name=...) 过滤（mcp_connect 只注册指定服务器）；M5 新增 McpGateway.status() 只读快照（mcp_list 不再摸私有成员）；M6 connect/register 动作入审计；M7 MCP 输出观察限长 2000 + artifacts.full_content 全量
- 文档：白名单默认关明示（gateway + learning/13）；竞品文档 v1.1（决策时点快照标注 + MCP/Skills/多Agent 已落地 + DSH star 改定性 + 措辞留余地）；归档 docs/engineering/07-code-review-r6.md
- flaky 修复：list_facts ORDER BY updated_at DESC, rowid DESC 确定性 tie-breaker（test_mem_recall_is_budgeted 14/14 × 3 稳定）
- 测试：新增 8 个 MCP 回归（M1-M7），全量 160 全绿，ruff/black 干净

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
