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
- **前端入口闭环 + 能力盘点（已交付，2026-08-28）**：services/agent_runtime/routes/capabilities.py——/v1/capabilities/{tools,skills,skills/{name},mcp,subagent} 只读路由（工具注册表 JSON-Schema / 技能指令+资源全文 / MCP 状态快照 / 多 Agent 活跃+记录），可选依赖未装配返回空态（注入式测试不炸）；app.py 挂载（skill_registry 提升到 create_app 作用域）。前端 CapabilitiesView（四页签：工具/技能/MCP/多 Agent）+ ApiView（OpenAI 兼容 Playground + /v1/models + curl/CLI/SDK 示例）；侧栏死占位项"技能·轨迹·工具"修复为可点「能力」+ 新增「开发者」。治理原则：**每个已交付能力 = 一个 REST 端点 + 一个前端视图**（死代码治理）。全量 178 测试全绿(新增6: test_capabilities), ruff/black 干净, tsc(strict)+vite build 通过, 真实服务器冒烟打通(13 工具/skills/subagent/models/chat.completions)。learning/11 §10 已写。
- **人机协作审批 + 工具权限分级（已交付，2026-08-29，F1.3/F2.4）**：权限分级——Tool.permission（read/write/destructive，默认 read），echo=read、sandbox_run=destructive；ApprovalPolicy（默认 destructive 及以上需审批，FLARE_APPROVAL_REQUIRE_LEVEL 可收紧到 write、extra_tools 白名单、approval_timeout 超时）。审批门=编排层横切能力（不塞 ToolRegistry.execute）：graph tool_executor 执行敏感工具前 interrupt({type:approval,...}) 挂起 → tasks._execute 两段式流（astream 在 __interrupt__ 后结束 → 登记审批 + 状态 awaiting_approval + asyncio.Event 等待 → Command(resume) 同 config 续跑）；批准放行执行 / 拒绝回灌 APPROVAL_REJECTED 观察（agent 换路）/ 超时自动拒绝（timed_out）。审批 API routes/approval.py：GET /v1/approvals(?pending_only) + GET {id} + POST {id}/decide（重复决策 409、未知 404）。SSE 新增 approval / approval_decision 事件；前端 ChatView 审批卡片（批准/拒绝按钮 + 状态回灌）+ App.tsx SSE 处理 + Sidebar awaiting_approval 黄点 + api.ts listApprovals/decideApproval。mock 加「沙箱执行」演示触发器（本地走通批准/拒绝闭环）。教学文档 learning/16。全量 190 测试全绿(新增12: test_approval), ruff/black 干净, tsc/vite build 通过, 真实服务器冒烟打通（批准真沙箱执行输出/拒绝 APPROVAL_REJECTED 收尾/SSE 重放/重复决策 409）。坑：①LangGraph interrupt 是一次性流——第一轮流在 __interrupt__ 后结束，resume 必须拆成第二段 astream 且用同一 thread_id config；②审批超时是安全网（默认 300s 自动按拒绝）；③asyncio.Event 单进程（多实例审批需 Redis pub/sub，M5 TODO）；④真实服务器冒烟用 Python httpx（Windows curl --data @file 会把 UTF-8 载荷解码错）；⑤uvicorn 入口是 agent_runtime.main:app 不是 .app（.app 无模块级 app）。
- **TOFU + 多实例审批后端 + 审批中心（已交付，2026-08-29，F1.3/F2.4 进阶）**：TOFU（首用信任）——同作用域（默认=会话线程，FLARE_APPROVAL_TOFU_SCOPE=thread|tenant|off）某工具获批一次后后续调用自动放行（免 interrupt 直行）；信任记录由 ApprovalManager 统一门控（决策获批才记，拒绝/超时/TOFU 关闭都不记），图内 requires_approval(scope) 先查策略再查信任集。多实例后端（ApprovalBackend 抽象）——Local（进程内 asyncio.Event，默认）+ Redis（请求 hash + 待审批 set + 有序索引 zset + TOFU 信任 set，跨节点决策轮询唤醒免 pub/sub，FLARE_APPROVAL_BACKEND=redis；连不上 fail-fast 优雅降级任务 failed）。graph/tasks/routes 全 async 化 + approval_scope 透传。审批中心（ApprovalsView 独立工作区：历史台账 + 待审批 5s 自动刷新 + 批准/拒绝 + 决策人/原因/时间；Sidebar「审批」导航待审批徽标脉冲；App 8s 轮询）。learning/16 补七~十章。全量 200 测试全绿(新增10: TOFU 信任/关闭/拒绝不记信任/作用域解析/Redis 跨实例决策+超时+索引/manager 经 Redis 端到端/图内 TOFU 免第二次 interrupt/任务同线程续聊免审批), ruff/black 干净, tsc/vite build 通过。冒烟：同线程任务1 审批→批准→任务2 免审批直行(saw_awaiting=False) + 审批历史仅1条；FLARE_APPROVAL_BACKEND=redis 无 Redis 时任务优雅 failed。坑：后端 decide 不再自动记信任（移到 manager 门控）；审批中心/卡片里反引号模板串会截断 run_code 外层模板（写 TSX 内容禁用反引号，用字符串拼接）。
- **模型配置与供应商接入（已交付，2026-08-29，M4 wiring 修复 + 控制台「模型」页）**：**关键修复**——create_app 构造 TaskManager 从未传 llm，真实服务永远跑 MockModelProvider，填了 FLARE_MODEL_API_KEY 也不生效（能力层做了/链路没接=死代码）；现按 build_provider(model_store.to_settings()) 装配。ModelConfigStore（agent_runtime/model_config.py）：生效优先级 **真实 env > 本地 JSON(data/model_config.json) > pydantic(.env)**；原子落盘+0600；env 名按 Settings 属性映射（FLARE_MODEL_PROVIDER 非 FLARE_PROVIDER）。REST routes/model.py：GET /v1/settings/model（脱敏，key 永不回传，只回 has_api_key/api_key_source）+ PUT（部分更新，api_key 空串=清除）+ GET presets（OpenAI/DeepSeek/通义百炼/硅基流动/Ollama/vLLM/自定义）+ POST test（临时覆盖，GET {base}/models 验端点+鉴权；anthropic 走 /v1/models + x-api-key）。热生效：PUT 后 task_manager.set_llm 重建网关（新建任务生效，运行中不受影响）。**Anthropic 原生协议（2026-08-30）**：model_gateway/anthropic_compat.py（Claude Messages API /v1/messages + anthropic-version 头，tool_use/tool_result 块配对、max_tokens 必填兜底、流式 text_delta；协议兼容默认 openai+anthropic）。前端 ModelSettingsView 重构（CC Switch 风格：供应商卡片网格 内置模拟/OpenAI/Anthropic/DeepSeek/… 点击即填 + 模型候选 chips 点击即选 + 协议 select mock|openai|anthropic）+ Sidebar「模型」导航。learning/17。**自定义供应商（2026-08-30）**：ModelConfigStore profiles（data/model_profiles.json，多配置可存可切，key 脱敏）+ routes GET/POST/PUT/DELETE /v1/settings/model/profiles + 前端「我的供应商」区（+ 自定义卡片/编辑/删除/点击激活）+ 模型目录 models[]（一个供应商多模型，chips 切换）+ 界面直接展示原始请求路径（POST {base}/v1/messages 或 /chat/completions，对齐 DSH）。全量 218 测试全绿(新增11: test_settings_model + 5: test_provider anthropic + 2: test_profiles)，ruff/black 干净，tsc/vite 通过。冒烟：GET 默认 mock -> PUT 保存(脱敏+落盘) -> GET 回读 -> test mock ok/openai+fake key 401(真实端点可达)/不可达 ConnectError -> 422 -> 清除，已还原干净 mock。坑：Settings 属性名是 model_provider 而本地字段是 provider（getattr 走映射表）；store 默认 path 必须从 settings.model_config_path 取否则测试串读真实文件；长中文文档用 Python heredoc 写更稳（模板字面量遇反引号/特殊字符解析炸）。
- **L6 token 级流式打字机（已交付，2026-08-30，参照 nova-agent 生效；commit c0ce385 + docs/learning/18）**：根因=4 层叠加——① actor 原用 llm.chat 一次性无流式；② 上游 OpenCode Zen 对 stream+tools 直接断连(ConnectError/All connection attempts failed)，**stream 不带 tools 稳定**（1 个最小探针确认）；③ 模型输出 JSON 决策（为工具调用）不能直接展示；④ 前端打字机被「text 变化重置 shown + result 立即 done」掐死；⑤ RetryProvider.stream 原不重试。修复：actor 改 llm.stream 收集决策（**stream 不带 tools**，工具 schema 在 system 提示，规避上游断连）+ stream 异常**自动降级 chat(带 tools) 兜底**（任务绝不因流式失败挂掉）；RetryProvider.stream **连接级重试**(ConnectError/ConnectTimeout/OSError/Timeout，流未消费可安全重试；中途断开不重放、交由上层降级)；模型 JSON 决策只在内部解析，把 decision.answer 按**自适应节奏拆段回放** on_token→task.events→SSE 新增 {"type":"token"} 事件（干净文本，短回复≥1s 可见、长回复封顶 2.5s）；前端 token 事件实时追加助手气泡 + StreamText **单调推进(不随 text 重置，30ms/2字符)** + step(final) 只对齐不置 done + **result 延迟 done**(min(5s, 500+字符*20ms)) + 会话/新任务切换重置 lastAssistantId/lastToolId（token 不串旧气泡）。验证：curl SSE 见 token 干净片段("你好，小明！"/"我是 Fla"…)+Playwright 真实 Chrome 逐字打出(6.5s→7.0s→7.5s 三段增长)+218 测试全绿+ruff/black/tsc/vite 干净。坑：①上游 stream+tools 兼容性**必须先最小探针**别假设；②模型输出 JSON 决策要"解析后回放 answer"不能直出 token；③打字机不可见根因通常是 done 时序+重置逻辑不是没流式；④curl 验证 SSE 的 data: 解析要 strip "event: xxx
" 前缀（块以 event: 开头）。
- **📚 里程碑现状（截至当前）**：M2 核心循环✅ → M3a 知识库✅ → M3b 分层记忆✅ → M3c RAG评测✅ → M4 模型网关+沙箱✅ → M5 云原生代码层✅ → M6 生产运营(SLO/告警/压测/门禁/回滚)✅ → Web 控制台(对话+知识库+记忆+运维+能力中心+开发者)✅ → MCP 客户端+Skills✅(FR-2/FR-3) → 多 Agent/Subagent 并行✅(F1.4) → Round 6 审查闭环 → CLI+OpenAI 兼容 REST API✅(F9.2/9.3) → **前端入口闭环✅（能力盘点 API + 能力中心/开发者视图）** → **人机协作审批+工具权限分级✅（F1.3/F2.4，审批门 interrupt + awaiting_approval + Web 审批卡片）** → **TOFU + 多实例审批后端 + 审批中心✅（F1.3/F2.4 进阶：首用信任免审 / Redis 跨节点 / ApprovalsView）** → **模型配置与供应商接入✅（M4 wiring 修复 + 控制台「模型」页 + Anthropic 原生协议✅ + 自定义供应商多配置✅）**（218 测试全绿） → **L6 token 级流式打字机✅（参照 nova-agent 生效：llm.stream + answer 拆段回放 + SSE token 事件 + 前端打字机可见，218 全绿，learning/18）** → **待办：服务器到位后的云部署(learning/05 §4.1 + 12 §7 回滚演练) + 压测实测容量**。教学文档 learning/01–16 齐（11=Web 控制台与产品 UX 已含 §10 前端入口闭环），索引在 docs/README.md；CHANGELOG.md 已全量沉淀 M1–M6+Web+UX+MCP/Skills+多Agent+Round6+CLI/REST+前端入口闭环+审批/权限。
- **功能盘点与竞品对比（2026-08-28 沉淀）**：docs/product/analysis/01-competitive-comparison.md——按 8 功能域对照 FR 盘点 + 与 Grok/Codex/DSH 对比。结论：运维治理/三层记忆/RAG评测/多租户领先；三大差距=MCP+Skills、多 Agent 并行、CLI/REST 接入。开发优先级=MCP/Skills → 多 Agent → CLI。
- **M5 云原生代码层（已交付，待服务器）**：多租户(flare_common/tenant.py X-Tenant-Id→contextvar→TaskRecord.tenant_id+to_dict+响应头回显),任务存储(agent_runtime/task_store.py TaskStore协议+InMemory+Sqlite+Redis,TaskManager写穿store+缓存防复活+stream从store轮询,FLARE_TASK_STORE=memory|sqlite|redis),PgVectorStore(rag/pgstore.py asyncpg+pgvector,纯函数SQL可测,连不上503),checkpoint生产分支(_create_pg_saver长连接AsyncPostgresSaver,CheckpointUnavailableError),reconcile(scripts/reconcile.py --fix双写对账),otel(flare_common/otel.py FLARE_OTEL_ENDPOINT空则no-op+exporter_factory可测),infra/(Dockerfile+.dockerignore+k8s 7清单:configmap/secret/deployment/service/hpa/ingress/otel-collector)。103测试全绿。坑：aiosqlite要row_factory=Row;AsyncPostgresSaver.from_conn_string是async CM不是awaitable;_save不能复活已删任务;_build_task_store在app.py;_DummySaver非合法checkpointer用MemorySaver。learning/05已更新M5交付段。
- **M4 模型网关+沙箱（已交付）**：model_gateway/{openai_compat(OpenAI 兼容 provider：wire 序列化重建 tool_calls+配对 tool_call_id、原生 tool_calls->call_tool 决策 JSON、纯文本->final、SSE 流式),gateway(RetryProvider 瞬态重试+build_provider 工厂 mock|openai)},graph.actor 每轮传 tools=_build_tools_json(registry)（原生 function-calling，_parse_decision 仍是唯一解析点）,sandbox/{runner(LocalProcessSandbox 子进程+超时+截断+POSIX 内存上限/DockerSandbox 生产占位 503 fail-fast),sandbox_tools(sandbox_run 工具 SANDBOX_TIMEOUT/SANDBOX_EXIT)},create_default_registry(sandbox=...) 接线,TaskManager.close(),FLARE_MODEL_NAME 配置。测试 17 个（test_provider/test_sandbox），全量 93 通过。坑：test_graph provider 需补 tools 参数；step_count=工具执行次数；API 测试同步函数用 time.sleep。
- **M3c RAG 评测（已交付）**：services/rag/eval/{metrics,dataset,runner,ragas}.py + hybrid.py（BM25+向量 RRF）+ rerank.py（CoverageReranker 开发/DashScopeReranker 生产 fail-fast）+ KnowledgeBase.search(strategy=vector|hybrid|hybrid_rerank) + POST /v1/kb/eval + scripts/demo_eval.py + 16 个新测试 + learning/09 教学文档。关键坑：rrf 覆盖赋值把 SearchHit 换成 KeywordHit（改首次赋值）；E501 把 CJK 按宽度 2 计（语料句子要短）；demo 用独立临时库不污染 kb.sqlite3。
- **learning 三架构教学文档（功能/业务/技术）**：06-功能架构（8 功能域地图/FR 功能清单/核心链路/依赖/NFR）、07-业务架构（价值主张/能力地图/业务流程/对象/角色/多租户/运营）、08-技术架构（选型/LangGraph ReAct 机制/数据架构 dev→prod/集成/部署高可用/安全/权衡）——均为"实践+真理"教学风格，与 06→08 互为上下游、交叉引用 product/architecture。
- **learning 教学文档扩展（开发+生产）**：新增 04-进阶开发指南（分层/加工具/加API/接真实模型/换存储底座/测试纪律踩坑合集/开发→生产切换矩阵）+ 05-生产部署指南（阿里云 ACK/OSS/PG/Redis/OTel/多租户/容量/SLO/回滚/上线清单，已实现✅与M5/M6⏳标注）；顺带修复 pyproject packages.find 缺 memory* 的部署阻断（wheel 不含 memory 包），pip install -e . 验证通过。
- **Round5 审查修复（M3b 交付）**：M1 三层记忆真正接线——TaskManager 从 checkpointer 取该线程近期对话传 build_context(recent=)，graph actor 支持同 thread 续聊追加新输入；M2 mem_recall 按相关度排序+封顶 k+2 条不再全量倾倒；M3 向量记忆溯源可读（文本前缀+短id）；M4 事实进上下文按最新 15 条封顶；M5 pgvector 迁移决策（同 PG 分表 kb_chunks/memory_chunks）；M6 thread_id 续聊语义文档化。pytest 60 全绿。
- **Round4 审查修复（M3a 交付）**：R1 工具 schema 经 system 消息注入（graph._build_tool_schema），真实模型才能自主调 kb_search（新增 test_agent_autonomously_calls_kb_via_system_schema）；R2 重复入库先删旧 chunk 再插；R3 content 上限 100k；R4 k 限 1..20 + 维度校验 VECTOR_DIM_MISMATCH；R6 暴露 HashEmbedder 字面非语义边界；R7 观察截断 200→300。pytest 56 全绿。
- 当前阶段：**M2 → M3a/b/c → M4 → M5 → M6 → Web 控制台 → MCP+Skills → 多 Agent/Subagent 并行 → Round 6 审查 → CLI+OpenAI 兼容 REST API（F9.2/9.3） → 前端入口闭环（能力中心+开发者） → 人机协作审批+工具权限分级（F1.3/F2.4） → TOFU+多实例审批后端+审批中心（F1.3/F2.4 进阶） → 模型配置与供应商接入（M4 wiring 修复 + 控制台「模型」页） 全部交付**（211 测试全绿）。下一步：**云部署 + 压测实测容量**（服务器到位后，learning/05 §4.1 + 12 §7 回滚演练）。

## 4. 已做决策（按时间倒序，最新在上）

| 时间 | 决策 |
| --- | --- |
| 2026-08-30 | ✅ **工作区 + 会话持久化已交付（对齐 DSH 产品形态第一步）**：工作区=会话命名空间（TaskRecord.workspace_id，默认 default）——Web 侧栏先选工作区再新建对话，会话按工作区分隔；前端无默认工作区（初始未选，必须先选/建工作区，Composer 禁用引导；创建工作区=后端目录 API（GET/POST /v1/workspaces/dirs 跨平台，对标 DSH host.listDirectory/createDirectory）+ 前端目录浏览对话框选服务器真实目录路径，输入自定义名字为次；workspace_id=真实路径）+ 每个工作区对话视图状态缓存（切换工作区保留不刷没，切回直接恢复 items/线程/草稿，不自动重连 SSE 防重复回放）；后端 POST /v1/tasks(workspace_id) + GET /v1/tasks?workspace= 过滤 + 新 GET /v1/workspaces 聚合（id+会话数+最近使用）+ SqliteTaskStore 加列（老库 ALTER 兼容迁移）；**task_store 默认 memory→sqlite**（会话列表落盘 data/tasks.sqlite3，重启可查）+ tests/conftest.py 测试隔离 memory（防污染真实库）+ 修复 recent/get/delete 从持久 store 读（重启后历史会话可查可删，跨重启验证）；222 测试全绿。下一步不变：云部署 + 压测实测容量 |
| 2026-08-30 | ✅ **L6 token 级流式打字机已交付（参照 nova-agent 生效）**：actor 用 llm.stream（stream 不带 tools 规避 OpenCode Zen 断连）+ 异常降级 chat 兜底 + RetryProvider.stream 连接级重试 + 决策 answer 拆段回放 on_token→SSE token 事件 + 前端打字机（StreamText 单调推进 + result 延迟 done + 会话切换重置 refs）；218 测试全绿 + Playwright 真实浏览器逐字打出验证；learning/18 + CHANGELOG + commit c0ce385。下一步不变：云部署 + 压测实测容量 |
| 2026-08-29 | ✅ **模型配置与供应商接入已交付**：M4 wiring 修复（create_app 真正装配 build_provider，填 key 才生效）+ ModelConfigStore（env>JSON>settings 优先级 + 脱敏，key 只在服务端）+ 控制台「模型」页（预设/保存/测试/清除）+ 保存热生效（set_llm）；211 测试全绿。下一步不变：云部署 + 压测实测容量 |
| 2026-08-29 | ✅ **TOFU + 多实例审批后端 + 审批中心已交付（F1.3/F2.4 进阶）**：TOFU 首用信任（同作用域获批后免 interrupt 直行，thread/tenant/off）+ ApprovalBackend 抽象（Local/Redis 跨节点轮询唤醒 + 信任集共享）+ ApprovalsView 审批中心（历史台账/集中决策/待审批徽标）；200 测试全绿。下一步不变：云部署 + 压测实测容量 |
| 2026-08-29 | ✅ **人机协作审批 + 工具权限分级已交付（F1.3/F2.4）**：Tool.permission 分级（sandbox_run=destructive）+ 编排层审批门（graph interrupt 挂起 → awaiting_approval → REST decide → Command(resume) 续跑）+ 审批 API（/v1/approvals 列表/详情/决策 409）+ Web 审批卡片 + SSE approval 事件 + 超时自动拒绝；190 测试全绿。下一步不变：云部署 + 压测实测容量 |
| 2026-08-28 | ✅ **MCP 客户端 + Skills 已交付（FR-2/FR-3）**：services/mcp（JSON-RPC 客户端 + 双传输 + 工具适配命名空间 + McpGateway 白名单/认证/审计）+ services/skills（SKILL.md 技能包 + SkillRegistry + skill_list/skill_load）；142 测试全绿。下一步：多 Agent 并行(F1.4) → CLI/REST 接入(F9.2/9.3) |
| 2026-08-28 | ✅ **多 Agent/Subagent 并行已交付（F1.4）**：services/subagent（SubagentRuntime 独立 ReAct 实例 + asyncio.gather 并行 + 预算/超时/并发护栏）+ spawn/await/list/run_subagents 工具；152 测试全绿。下一步：CLI(F9.2) + OpenAI 兼容 REST API(F9.3) → 云部署+压测 |
| 2026-08-28 | ✅ **Round 6 审查闭环（MCP 客户端）**：M1-M8 全部修复（图内 schema 冻结/SSE 分块/超时配置/register_all 过滤/status()/审计/截断/白名单文档）+ flaky 修复（rowid tie-breaker）+ 竞品文档 v1.1 + 归档 07-code-review-r6.md；160 测试全绿。下一步不变：CLI/REST(F9.2/9.3) → 云部署+压测 |
| 2026-08-28 | ✅ **CLI + OpenAI 兼容 REST API 已交付（F9.2/F9.3）**：/v1/chat/completions（标准 Chat Completions 契约 + stream SSE）+ /v1/models + OpenAI 风格错误 + FLARE_API_KEY 可选认证（复用 TaskManager，同步语义的异步执行）+ services/flare_cli（chat/tasks/task/models，console script flare）；172 测试全绿。下一步：云部署 + 压测实测容量 |
| 2026-08-28 | ✅ **前端入口闭环已交付**：能力盘点 REST（/v1/capabilities/{tools,skills,mcp,subagent} 只读）+ 前端能力中心（工具/技能/MCP/多 Agent 四页签）+ 开发者入口（OpenAI 兼容 Playground + curl/CLI/SDK 示例）；侧栏死占位项修复为可点「能力」；治理原则=一个能力一个 REST 端点一个前端视图（死代码治理）；178 测试全绿 + tsc/vite build + 真实服务器冒烟。下一步不变：云部署 + 压测实测容量 |
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
| 2026-08-31 | ✅ **Agent 代码工作区 P1（质变第一步）**：工作区=真实目录注入 agent 工具（对标 DSH）——registry.task_view(cwd) 每任务附加 read/write/edit/glob/grep/bash 六工具（workspace_tools.py，闭包绑定 cwd + 每任务独立 observed）；**read 前置策略**（覆盖已存在文件前必须 read；edit 版本 CAS 防盲改）；**越界检测**（write/edit 在 cwd 外拒绝 OUT_OF_BOUNDS）；bash=Git Bash（bash -c 每次全新进程、超时默认 30s/上限 120s、输出 64KB 截断、FLARE_SHELL 可覆盖）；权限 read/write/destructive 分级；**default/非目录 workspace 不注入**（防越权）；graph 集成测试（fake llm 驱动 read 全链路）通过；257 测试全绿。下一步（P2）：前端文件树侧栏 + Docker/bash 沙箱 + 越界审批 UI；或用户真实模型体验读/写/跑工作区 |
| 2026-08-31 | ✅ **前端美化 P1-P3 全交付**：Markdown 渲染（react-markdown + remark-gfm + rehype-highlight，代码块语言标签+复制按钮+行内代码）；气泡重构（用户渐变微光块/助手 done 后 Markdown 渲染 + streaming 打字机、入场动画 fade-in-up、实时消息时间戳 ts 可选）；Composer 自动增高+圆形渐变发送钮+聚焦光晕；ToolCallCard 展开/收起 grid-rows 过渡+运行呼吸边框+成功对勾 glow；WelcomePanel 动态问候轮换+建议卡 hover 上浮+渐变 Logo 呼吸；思考态 ThinkingStatus 阶段文字轮换（思考→分析→调用工具→执行）；styles.css 加 markdown-body 排版 + hljs token 暖色高亮；bundle gzip 131KB。构建+tsc 全过。**下一步：agent 执行侧优化（用户已确认）** |
| 2026-08-31 | 🔧 **修复 + DSH 仿照**：① Markdown 生效——AssistantBubble **流式期间即渲染 Markdown**（不再等 done 才切换，标题/代码即时可见）+ rehype-highlight 加 **detect:true**（无语言标签代码块自动检测高亮，如 bash）；② 侧栏工作区交互仿照 DSH `WorkspacePickFlow`——下拉=已有工作区列表 + footer **「添加工作区…」** 按钮（不再叫"打开文件夹"）；**无任何工作区时点击工作区按钮直接打开目录选择**（跳过空菜单）；**移除"输入自定义名字"输入框**（DSH 无此，只有目录选择一条路）；选择目录→createWorkspace 采纳→onPick 选中。构建 tsc 全过，服务已提供新 dist |
| 2026-08-31 | 🔧 **会话/工作区管理对齐 DSH（直接删除，不归档）**：后端 `TaskRecord.title` + `PATCH /v1/tasks/{id}` 重命名（只改显示名，task_input 保留）+ `DELETE /v1/workspaces/{id:path}` 删除工作区全部会话（不删目录，path 转换器容纳 / 与 \\）；侧栏会话行 hover 出 **MoreHorizontal 菜单 [重命名][删除]**（DSH rowActions 对齐），删除确认弹窗直接删（不归档）；会话标题 `t.title || autoTitle`；工作区行 hover 显示删除按钮 → 确认弹窗 → 清会话；删当前工作区回未选态。261 测试全绿 + HTTP 冒烟通过 |
| 2026-08-31 | 🔧 **会话级 权限模式 + 模型选择（对齐 DSH）**：后端 TaskRecord 加 `permission_mode`（read-only/approval/unrestricted，默认 approval）+ `model`（profile id，None=默认激活模型）；read-only = registry.read_only() 只注入 read/glob/grep（write/edit/bash 不注入）+ 免审批；unrestricted = 免审批全自动；approval = 现状审批门；per-task 模型经 `model_resolver`（ModelConfigStore.profile_to_settings + build_provider，无效回退默认，finally 关闭临时 provider）；TaskCreate 校验 pattern 非法 422。前端 Composer 顶部 chip 下拉：权限模式（锁/盾/闪电 + 描述 + 当前高亮）+ 模型（默认·激活模型 + 自定义供应商列表）；App 加载 listModelProfiles + getModelSettings，send 透传。265 测试全绿 + HTTP 冒烟通过 |
