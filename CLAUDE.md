# CLAUDE.md — Flare Agent 项目记忆

> 本文件是**项目持久记忆**。新会话 / 切换模型 / 换工具时，第一件事是读取本文件，
> 以恢复项目上下文，避免遗忘目标、约束、进度和已做决策。
> 维护规则：任何影响方向/架构/决策的变更，必须同步更新本文件（和 AGENTS.md）。

---

## 1. 项目一句话目标

构建一个**企业级、可上线、高可用、可拓展**的 AI Agent 平台，对标
OpenAI Codex / Claude Code / DeepSeek Harness，估算并发 **百万级**，部署在 **阿里云**，
对象存储用 **阿里云 OSS**，并集成 **RAG** 等最新 AI 能力。
**不是 demo，是要上生产、可运维、可管理的东西。**

## 2. 硬性要求（不可违背）

- ⚠️ **推送策略（2026-08-27 用户明确要求）**：默认**只在本地提交（git commit）**，**不主动推送远程仓库（不 push）**；只有用户明确要求时才 push。除非用户说"推送/提交到远程/发 PR"，一律只做本地提交。
- 生产级：可部署到真实服务，可监控、可运维、可回滚、可审计
- 高可用：多可用区、无单点、自动故障恢复
- 高并发：设计目标百万级并发（弹性的、按指标扩容；不追求"永远同时百万活跃"的虚数字）
- 可拓展：组件化、插件化（Tools / MCP / Skills / RAG 均可插拔），多模型可路由
- 技术栈：用**最强企业级技术**，接受云原生全家桶（K8s、消息队列、向量库、观测体系）
- 存储：**阿里云 OSS** 作为对象存储（代码快照、技能包、RAG 文档源、日志归档等）
- 必备 AI 能力：RAG（向量检索 + 混合检索 + 重排）、MCP 工具协议、Skills、工具系统、沙箱执行、记忆体系
- 面向人群：已掌握 demo 级 AI 开发（模型/上下文/记忆/工具/MCP/Skills 已入门），需要的是**进阶+上线**

## 3. 项目信息

- 工作区：`/d/Data/deepseekharness_project/flare-agent`（文件工具用 `D:\Data\...`，bash 用 `/d/Data/...`，两套路径格式不同！）
- **Python 环境（2026-08-27 用户明确）**：用 **conda 环境 `flare-agent`**（Python 3.12，与 CI 一致），**不用 .venv**；命令统一 `conda run -n flare-agent python ...`（等价 Makefile 的 `make test/lint/dev`）。conda 根：D:\software\conda，环境目录 D:\software\conda-envs\envs
- GitHub：仓库 `Syotick/flare-agent`（gh 已认证，账号 Syotick；**2026-08-27 由用户要求转为公开**，公开前已做敏感信息扫描）
- 版本控制：git，主分支 `main`，中文 commit message 允许（团队用中文）；PR 分支规范见 docs/engineering
- ⚠️ **GitHub 流程已启用（2026-08-27）**：main 已开**分支保护**——直推 main 会被拒绝（admin 可绕过），必须走 `feat/*` 分支 + PR；PR 需通过 CI 门禁（status check: `Required Status Gate`）。合并方式：squash/rebase（已禁 merge commit）。仓库已配：LICENSE(MIT)/CONTRIBUTING/CODE_OF_CONDUCT/SECURITY/Issue&PR 模板/ci/release/stale/dependabot/pre-commit/labels/milestones(M1-M6)
- 📚 **文档体系（2026-08-27 重构）**：docs/README.md 是**唯一入口**；product(调研/需求/架构) / engineering(开发规范) / learning(面试) / adr / templates / guides 分类；开发文档与产品文档分离；**改 docs 影响方向时必须同步 CLAUDE.md**（规则见 docs/README §6）。
- ✅ **CI 现状（2026-08-27）**：main 上 CI 全绿（lint/test/scan/gate），PR #1 已走通全流程。已移除 CodeQL（私有仓库未启用 code scanning 且暂无代码）——待有代码且开启 code scanning 再补回。Dependabot 在无 manifest 时会产生 benign 失败 run，属正常。
- 🌐 **网络**：git 直连 github.com 会失败，需走代理（已配 `git config --global http.proxy http://127.0.0.1:7890`，Clash 端口）；gh 走 api.github.com 无需代理。
- 💡 **踩坑经验**：① GitHub Actions 的 YAML 里内联 `run: echo "TODO: xxx: yyy"` 这种「值含冒号+空格」必须用 block scalar（`run: |`），否则 workflow 解析失败（run 0 秒失败、workflow 名变文件路径）。② 分支保护的 required status check context 必须与 GitHub 实际生成的 check-run 名称一致——本项目是 `Required Status Gate`（不是 `CI / Required Status Gate`），名称不匹配会导致 PR mergeStateStatus=BLOCKED。③ gitleaks-action@v2 在 PR 模式需要 workflow `permissions: pull-requests: read`，否则 403。
- **开发规范（强制）**：docs/engineering/01-development-standards.md（分支/提交/评审/测试/CI-CD/发布/SRE/安全）
- **代码审查（2026-08-27 起）**：R1=engineering/03（18项）；R2=engineering/04（F1-F4）；R3=engineering/05（Web前端 L1-L4+问题2/3，真流式/SSE生命周期/折叠滚动/刷新恢复）；后续每轮审查结果都归档到 engineering/
- **M2 代码结构（2026-08-27）**：services/ 已开工——共享库 flare_common + agent_runtime(LangGraph ReAct 图 + 任务API **POST 立即返回202 + SSE 真流式 + GET 详情/列表/DELETE 删除**) + tools_gateway + model_gateway + **web Console(Vite+React+TS)** + rag/sandbox 占位；pip install -e . 可安装；pytest 32 全绿，ruff/black 干净；make web-dev/web-build 管前端
- **Web 前端栈（2026-08-27 定，参考 nova-agent D:/Data/.../nova-agent/src）**：Vite5 + React18 + **Tailwind v4(@tailwindcss/vite) + shadcn 风格(Radix: alert-dialog/dropdown-menu) + lucide-react 图标** + cva/clsx/tailwind-merge；**flare 耀斑主题**（styles.css @theme 琥珀金令牌 + 太阳日冕径向渐变背景 + 灰烬粒子 + corona-drift/辉光动画）；组件：FlareLogo(SVG太阳+日珥轨道)/ThinkingOrb/FlareLogo 思考光球/Sidebar(品牌+会话搜索分组+删除确认AlertDialog+导航+状态)/Composer(工具栏+autosize textarea+渐变发送/停止)/ChatView(用户/助手气泡+StreamText打字机+ToolCallCard药丸折叠)/WelcomePanel(示例卡)/ui 组件(button/input/card/alert-dialog/dropdown-menu)；后端 API：GET /v1/tasks、DELETE /v1/tasks/{id}、POST/SSE；包体：CSS gzip 7KB(仅用到的类)+JS 分包(vendor-react/radix/lucide/ui)
- **Web UX 修复（已交付）**：Composer 移除对用户暴露的 max_steps/thread_id（内部常量 MAX_STEPS=8；thread_id 全自动：send 同步服务端生成的 thread_id、pickTask 沿用会话线程、newChat/hash 恢复分别清空/续用）；会话切换修复：pickTask 先 setItems([]) 再 SSE 回放，避免旧会话消息残留；hash 恢复也回放轨迹并续线程。
- **Web 运维中心页（已交付）**：OpsView.tsx 接 /v1/ops/slo——三个 SLO 卡片(目标/错误预算进度条/告警分级徽章 none|P2|P0) + 整体状态横幅 + /metrics 原始指标折叠 + 15s 自动刷新；Sidebar 新增"运维(M6)"导航；ViewId 加 ops。构建后 8000 直接看 http://127.0.0.1:8000/。
- **Web 控制台管理页（已交付）**：services/web React+Vite+Tailwind。新增知识库管理页(components/KnowledgeBaseView.tsx：入库/文档列表+删除/hybrid检索/RAG评测proxy)与记忆管理页(components/MemoryView.tsx：事实CRUD+向量记忆检索+上下文块预览)；App.tsx 加 view 切换(chat|kb|memory)；Sidebar 工作区导航可点(对话/知识库/记忆)；api.ts 加 KB/Memory 客户端函数。构建 npm run build → dist（已 gitignore），后端 8000 挂载 / 静态服务，浏览器 http://127.0.0.1:8000/（不用 3080，DSH 占用）。坑：长 heredoc 写 TSX 会被 run_code 截断污染文件 → 分段<100行写并核对行数；noUnusedLocals 要删未用图标导入。
- **M6 生产运营（已交付）**：metrics.py 纯 Python Prometheus 指标注册表(/metrics 端点,零依赖) + HTTP 中间件埋点 + 任务结果埋点；slo.py(SLO/错误预算/燃烧速率/多窗口告警分级 14.4x/36x, FLARE_SLO_* 可调)；/v1/ops/slo + /v1/ops/error-budget；infra/k8s 08-prometheus-rules + 09-alertmanager(P0→page/P2→slack) + 10-service-monitor；scripts/loadtest.py(进程内 mock 或 --url 打流量, p50/p95/p99 vs SLO, 报告+退出码门禁)、release_gate.py(健康+版本+错误预算放行/阻断)、alert_check.py(在线+离线燃烧速率演练)；learning/12 runbook。121 测试全绿, ruff/black 干净。坑：dev SQLite checkpointer 长连接锁文件→本地脚本注入 MemorySaver(loadtest 已内置)；压测/冒烟别跟运行中 :8000 服务抢同一 sqlite。
- **MCP 客户端 + Skills（已交付，2026-08-28，FR-2/FR-3）**：services/mcp——protocol(JSON-RPC 2.0 零依赖)+client(McpClient: initialize握手/tools/list/tools/call, 双传输 Streamable HTTP+SSE, httpx, 协议层与传输层分离)+adapter(MCP工具→Tool 命名空间 mcp__<server>__<tool>, inputSchema 复用统一校验)+gateway(McpGateway: 多服务器/白名单/认证头注入/审计/幂等注册, FLARE_MCP_SERVERS JSON 配置)+mcp_tools(mcp_connect按需连接+注册/mcp_list)+testing(FakeTransport+MemoryMcpServer stdlib 真实HTTP双形态零依赖)。services/skills——frontmatter(零依赖YAML子集)+loader(Skill: 指令+resources+required_tools)+registry(安装/卸载/列表/build_context 上下文注入)+skill_tools(skill_list/skill_load)。示例技能 examples/skills/code-review；demo 脚本 scripts/demo_mcp.py/demo_skills.py。142 测试全绿(新增22), ruff/black 干净。坑：①长 heredoc 写代码\n 会被 JS 转义成真换行污染字符串→写文件用 \\n 或 chr(10)/+拼接；②pyproject packages.find 又缺包(这次 mcp*/skills*)→已补(同 memory* 坑)；③SSE endpoint 相对路径要用 urljoin 解析。learning/13 已写。
- **多 Agent/Subagent 并行（已交付，2026-08-28，F1.4）**：services/subagent——SubagentRuntime(子任务=独立 ReAct Agent 实例复用 build_react_agent+MemorySaver 临时 checkpointer, 进程内 asyncio 后台任务并发, 独立 max_steps/独立超时 timed_out/存活上限 MAX_ACTIVE=64, spawn/await(shield 超时不打断)/run_subagents(asyncio.gather 并行收集)/list/close)；编排工具 spawn_subagent/await_subagent/list_subagents/run_subagents(并行核心原语, 单次上限16 prompt)；create_app 接线(共享父 llm/registry, TaskManager 加 llm/registry 属性)。demo 脚本 scripts/demo_subagent.py；learning/14。152 测试全绿(新增9, 含 max_active>=2 证真并发+超时护栏), ruff/black 干净。坑：async def 不能内联在表达式里(测试里要先定义函数)。
- **Round 6 审查已闭环（2026-08-28，MCP 客户端）**：归档 docs/engineering/07-code-review-r6.md。M1 图内工具 schema 冻结 → graph.actor 每轮重建 system 工具清单(原位替换, mcp_connect 中途注册的新工具同任务可见可调)+ReAct 图端到端用例；M2 SSE 跨 chunk 拆分 → _split_sse_events 增量切分(残余保留 buffer)+sse_chunk 分块测试；M3 超时可配 → McpServerConfig.timeout→_make_client→build_transport 透传(此前 McpClient._timeout 实际未达传输层)；M4 register_all(server_name=...)过滤；M5 McpGateway.status() 只读(不再摸私有成员)；M6 connect/register 入审计；M7 MCP 输出观察限长2000+artifacts.full_content；M8 白名单默认关明示。坑：①202 无 Content-Length 时 httpx 等连接关闭才返回(阻塞≈服务器处理时长)→202 显式 Content-Length:0；②SSE 测试服务器分块写用 handler 的 wfile(不是 server 对象)；③test_mem_recall_is_budgeted flaky 根因=time.time() 碰撞致 updated_at 等值排序不确定→list_facts ORDER BY updated_at DESC, rowid DESC 确定性 tie-breaker(已修复, 14/14×3)。竞品文档 v1.1：标注决策时点快照+落地进度引用, DSH star 改定性("现象级增长", 公开报道上线数小时破3.3万星), 措辞留余地("骨架齐, 能力逐项落地")。全量 160 测试全绿(新增8 MCP 回归), ruff/black 干净。
- **CLI + OpenAI 兼容 REST API（已交付，2026-08-28，F9.2/F9.3）**：services/agent_runtime/routes/openai_compat.py——POST /v1/chat/completions（标准 Chat Completions 契约：非流式 + stream=true SSE 分块 + [DONE]）+ GET /v1/models；复用 TaskManager（同一套登记/可观测/可查，非流式内部轮询=同步语义的异步执行）；OpenAI 风格扁平错误 {"error":{message,type,param,code}}（自定义 OpenAICompatError→JSONResponse，不经 FastAPI detail 包装——HTTPException 会被包成 {"detail":...} 不符合契约，坑）；可选认证 FLARE_API_KEY(Bearer, 空=开放, 生产必配)；Settings 加 api_key。services/flare_cli——FlareClient(httpx 瘦客户端, 可注入 ASGITransport 直连应用测试不启真实服务器) + main(argparse: chat 流式/--json/tasks/task(--stream)/models) + pyproject [project.scripts] flare 与包 flare_cli*(记得加 include, 老坑)；.env.example 补 FLARE_API_KEY/FLARE_URL。冒烟验证：真实 uvicorn + python -m flare_cli 三端(chat 流式/tasks/--json)端到端打通。全量 172 测试全绿(新增12: test_openai_compat 6 契约/流式/错误/认证 + test_flare_cli 5 + 复用), ruff/black 干净。learning/15 已写。
- **📚 里程碑现状（截至当前）**：M2 核心循环✅ → M3a 知识库✅ → M3b 分层记忆✅ → M3c RAG评测✅ → M4 模型网关+沙箱✅ → M5 云原生代码层✅ → M6 生产运营(SLO/告警/压测/门禁/回滚)✅ → Web 控制台(对话+知识库+记忆+运维)✅ → MCP 客户端+Skills✅(FR-2/FR-3) → 多 Agent/Subagent 并行✅(F1.4) → Round 6 审查闭环 → **CLI+OpenAI 兼容 REST API✅(F9.2/9.3)**（172 测试全绿） → **待办：服务器到位后的云部署(learning/05 §4.1 + 12 §7 回滚演练) + 压测实测容量**。教学文档 learning/01–15 齐（15=OpenAI 兼容 API 与 CLI），索引在 docs/README.md；CHANGELOG.md 已全量沉淀 M1–M6+Web+UX+MCP/Skills+多Agent+Round6+CLI/REST。
- **功能盘点与竞品对比（2026-08-28 沉淀）**：docs/product/analysis/01-competitive-comparison.md——按 8 功能域对照 FR 盘点 + 与 Grok/Codex/DSH 对比。结论：运维治理/三层记忆/RAG评测/多租户领先；三大差距=MCP+Skills、多 Agent 并行、CLI/REST 接入。开发优先级=MCP/Skills → 多 Agent → CLI。
- **M5 云原生代码层（已交付，待服务器）**：多租户(flare_common/tenant.py X-Tenant-Id→contextvar→TaskRecord.tenant_id+to_dict+响应头回显),任务存储(agent_runtime/task_store.py TaskStore协议+InMemory+Sqlite+Redis,TaskManager写穿store+缓存防复活+stream从store轮询,FLARE_TASK_STORE=memory|sqlite|redis),PgVectorStore(rag/pgstore.py asyncpg+pgvector,纯函数SQL可测,连不上503),checkpoint生产分支(_create_pg_saver长连接AsyncPostgresSaver,CheckpointUnavailableError),reconcile(scripts/reconcile.py --fix双写对账),otel(flare_common/otel.py FLARE_OTEL_ENDPOINT空则no-op+exporter_factory可测),infra/(Dockerfile+.dockerignore+k8s 7清单:configmap/secret/deployment/service/hpa/ingress/otel-collector)。103测试全绿。坑：aiosqlite要row_factory=Row;AsyncPostgresSaver.from_conn_string是async CM不是awaitable;_save不能复活已删任务;_build_task_store在app.py;_DummySaver非合法checkpointer用MemorySaver。learning/05已更新M5交付段。
- **M4 模型网关+沙箱（已交付）**：model_gateway/{openai_compat(OpenAI 兼容 provider：wire 序列化重建 tool_calls+配对 tool_call_id、原生 tool_calls->call_tool 决策 JSON、纯文本->final、SSE 流式),gateway(RetryProvider 瞬态重试+build_provider 工厂 mock|openai)},graph.actor 每轮传 tools=_build_tools_json(registry)（原生 function-calling，_parse_decision 仍是唯一解析点）,sandbox/{runner(LocalProcessSandbox 子进程+超时+截断+POSIX 内存上限/DockerSandbox 生产占位 503 fail-fast),sandbox_tools(sandbox_run 工具 SANDBOX_TIMEOUT/SANDBOX_EXIT)},create_default_registry(sandbox=...) 接线,TaskManager.close(),FLARE_MODEL_NAME 配置。测试 17 个（test_provider/test_sandbox），全量 93 通过。坑：test_graph provider 需补 tools 参数；step_count=工具执行次数；API 测试同步函数用 time.sleep。
- **M3c RAG 评测（已交付）**：services/rag/eval/{metrics,dataset,runner,ragas}.py + hybrid.py（BM25+向量 RRF）+ rerank.py（CoverageReranker 开发/DashScopeReranker 生产 fail-fast）+ KnowledgeBase.search(strategy=vector|hybrid|hybrid_rerank) + POST /v1/kb/eval + scripts/demo_eval.py + 16 个新测试 + learning/09 教学文档。关键坑：rrf 覆盖赋值把 SearchHit 换成 KeywordHit（改首次赋值）；E501 把 CJK 按宽度 2 计（语料句子要短）；demo 用独立临时库不污染 kb.sqlite3。
- **learning 三架构教学文档（功能/业务/技术）**：06-功能架构（8 功能域地图/FR 功能清单/核心链路/依赖/NFR）、07-业务架构（价值主张/能力地图/业务流程/对象/角色/多租户/运营）、08-技术架构（选型/LangGraph ReAct 机制/数据架构 dev→prod/集成/部署高可用/安全/权衡）——均为"实践+真理"教学风格，与 06→08 互为上下游、交叉引用 product/architecture。
- **learning 教学文档扩展（开发+生产）**：新增 04-进阶开发指南（分层/加工具/加API/接真实模型/换存储底座/测试纪律踩坑合集/开发→生产切换矩阵）+ 05-生产部署指南（阿里云 ACK/OSS/PG/Redis/OTel/多租户/容量/SLO/回滚/上线清单，已实现✅与M5/M6⏳标注）；顺带修复 pyproject packages.find 缺 memory* 的部署阻断（wheel 不含 memory 包），pip install -e . 验证通过。
- **Round5 审查修复（M3b 交付）**：M1 三层记忆真正接线——TaskManager 从 checkpointer 取该线程近期对话传 build_context(recent=)，graph actor 支持同 thread 续聊追加新输入；M2 mem_recall 按相关度排序+封顶 k+2 条不再全量倾倒；M3 向量记忆溯源可读（文本前缀+短id）；M4 事实进上下文按最新 15 条封顶；M5 pgvector 迁移决策（同 PG 分表 kb_chunks/memory_chunks）；M6 thread_id 续聊语义文档化。pytest 60 全绿。
- **Round4 审查修复（M3a 交付）**：R1 工具 schema 经 system 消息注入（graph._build_tool_schema），真实模型才能自主调 kb_search（新增 test_agent_autonomously_calls_kb_via_system_schema）；R2 重复入库先删旧 chunk 再插；R3 content 上限 100k；R4 k 限 1..20 + 维度校验 VECTOR_DIM_MISMATCH；R6 暴露 HashEmbedder 字面非语义边界；R7 观察截断 200→300。pytest 56 全绿。
- 当前阶段：**M2 → M3a/b/c → M4 → M5 → M6 → Web 控制台 → MCP+Skills → 多 Agent/Subagent 并行 → Round 6 审查 → CLI+OpenAI 兼容 REST API（F9.2/9.3） 全部交付**（172 测试全绿）。下一步：**云部署 + 压测实测容量**（服务器到位后，learning/05 §4.1 + 12 §7 回滚演练）。

## 4. 已做决策（按时间倒序，最新在上）

| 时间 | 决策 |
| --- | --- |
| 2026-08-28 | ✅ **MCP 客户端 + Skills 已交付（FR-2/FR-3）**：services/mcp（JSON-RPC 客户端 + 双传输 + 工具适配命名空间 + McpGateway 白名单/认证/审计）+ services/skills（SKILL.md 技能包 + SkillRegistry + skill_list/skill_load）；142 测试全绿。下一步：多 Agent 并行(F1.4) → CLI/REST 接入(F9.2/9.3) |
| 2026-08-28 | ✅ **多 Agent/Subagent 并行已交付（F1.4）**：services/subagent（SubagentRuntime 独立 ReAct 实例 + asyncio.gather 并行 + 预算/超时/并发护栏）+ spawn/await/list/run_subagents 工具；152 测试全绿。下一步：CLI(F9.2) + OpenAI 兼容 REST API(F9.3) → 云部署+压测 |
| 2026-08-28 | ✅ **Round 6 审查闭环（MCP 客户端）**：M1-M8 全部修复（图内 schema 冻结/SSE 分块/超时配置/register_all 过滤/status()/审计/截断/白名单文档）+ flaky 修复（rowid tie-breaker）+ 竞品文档 v1.1 + 归档 07-code-review-r6.md；160 测试全绿。下一步不变：CLI/REST(F9.2/9.3) → 云部署+压测 |
| 2026-08-28 | ✅ **CLI + OpenAI 兼容 REST API 已交付（F9.2/F9.3）**：/v1/chat/completions（标准 Chat Completions 契约 + stream SSE）+ /v1/models + OpenAI 风格错误 + FLARE_API_KEY 可选认证（复用 TaskManager，同步语义的异步执行）+ services/flare_cli（chat/tasks/task/models，console script flare）；172 测试全绿。下一步：云部署 + 压测实测容量 |
| 2026-08-27 | 仓库 flare-agent 已公开；monorepo：services/(flare_common 共享库 + agent_runtime/model_gateway/tools_gateway/rag/sandbox) + infra + eval + tests；模块化单体优先(ADR-0015)，可 pip install -e . |
| 2026-08-27 | 共享库命名 flare_common（带命名空间、可独立安装），对齐按服务拆分演进（审查 D1） |
| 2026-08-27 | 记忆体系：CLAUDE.md + AGENTS.md 双写；docs/ 已按分类重构：product(调研/需求/架构)/engineering(开发规范)/learning(面试)/adr/templates，入口 docs/README.md |
| 2026-08-27 | 技术方向初选（待评审）：Agent 运行时主语言 **Python**（生态最强，LangGraph/CoAgents 等）；控制面可 TS |
| 2026-08-27 | 对象存储定为**阿里云 OSS**；向量库候选 Milvus/Qdrant/pgvector（需求评审时定夺） |
| 2026-08-27 | 并发目标表述统一为：**可弹性扩展到百万级并发接入**，不承诺恒定百万在线 |
| 2026-08-27 | ✅ 技术栈**定稿**：Python + LangGraph + FastAPI + Milvus（主选）；模型网关自研(OpenAI 兼容)；推理可自托管 vLLM/SGLang |
| 2026-08-27 | ✅ 产品形态：**本地 Web 优先**（Web 控制台 + 预留 CLI/API） |
| 2026-08-27 | ✅ 沙箱路线：**"最能秀肌肉"的强隔离**——微虚拟化级（Kata Containers / Firecracker microVM），本地开发用 Docker 降级模式，架构上沙箱可插拔 |
| 2026-08-27 | ✅ 阿里云凭证**后续提供**：开发阶段用本地模拟（MinIO 模拟 OSS、本地 Redis/PG/向量库），存储层做成可切换 Provider |
| 2026-08-27 | ✅ 新增需求：**面试题驱动开发**——全面覆盖高级 Agent 工程师考点（多路召回/GraphRAG/记忆/安全/高并发等），实践(落地代码)+真理(理论)并重 |

## 5. 待决策 / 待用户确认（剩余阻塞点）

1. ~~技术栈~~ ✅ 已定（Python+LangGraph+Milvus）
2. 阿里云账号/凭证：**后续提供**，先用本地模拟开发，不阻塞
3. ~~产品形态~~ ✅ 本地 Web 优先
4. ~~沙箱~~ ✅ Kata/Firecracker 强隔离（开发期 Docker 降级）
5. 预算与模型供应商（阿里云百炼？OpenAI/Claude/DeepSeek 自接？）——开发先默认 DeepSeek/通义兼容接口 + 可配置多供应商
6. ~~沙箱合规~~ ✅ 按企业级微虚拟化做
7. 团队规模与运维人力（决定自动化程度）——暂按单人全栈推进

## 6. 里程碑（详细版见 docs/product/requirements/01-development-requirements.md §6）

- M0 项目准备（Git/仓库/文档/记忆）✅
- M1 需求与架构评审 ✅（ADR ×15、模块设计、压测方案、评审记录）
- M2 核心 Agent 引擎（agent loop + 工具系统 + 会话）🔨 核心闭环 ✅（工具/ReAct/任务API/SSE/Web Console）
- M3 RAG 知识库 + 记忆体系
- M4 多模型路由 + 推理服务 + 成本控制
- M5 云原生部署（阿里云 ACK + OSS + 可观测）+ 压测
- M6 上线、灰度、SLO 运营

## 7. 常用命令备忘

```bash
# 推送
git add -A && git commit -m "msg" && git push origin main
# 创建私有仓库（如已删）
gh repo create flare-agent --private --source . --remote origin --push
# 当前分支
git branch --show-current
```

## 8. 铁律（编码约束）

- 任何密钥/凭证**绝不入库**（见 .gitignore），一律走环境变量 / K8s Secret / Vault
- 用户数据（代码快照、RAG 文档、会话）先落 OSS/持久化，内存只做缓存
- 所有外部依赖评估生产化程度（维护活跃度、许可证、云上托管能力）后再引入
- 面向百万并发：有状态东西尽量外置（Redis/DB/消息队列），应用层无状态、水平扩展
