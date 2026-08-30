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

## 已确认决策（2026-08-27 / 2026-08-28 / 2026-08-29 / 2026-08-30）
- 2026-08-30：**工作区 + 会话持久化已交付**（对齐 DSH 产品形态第一步）——工作区=会话命名空间（workspace_id 默认 default）；Web 侧栏先选工作区再新建对话、会话按工作区分隔；前端无默认工作区（初始未选，先选/建工作区才可对话；创建工作区=后端目录 API + 前端目录浏览对话框选服务器真实路径（对标 DSH browse；workspace_id=真实路径））+ 每工作区对话视图状态缓存（切换保留不刷没，切回恢复，不自动重连 SSE 防重复）；后端 POST /v1/tasks(workspace_id) + GET /v1/tasks?workspace= 过滤 + GET /v1/workspaces 聚合 + SqliteTaskStore 加列迁移；**task_store 默认 memory→sqlite**（data/tasks.sqlite3 落盘，重启会话列表可查）+ tests/conftest.py 测试隔离 memory + 修复 recent/get/delete 从持久 store 读（重启后历史会话可查可删，跨重启验证）；222 测试全绿。下一步 = 云部署 + 压测实测容量
- 2026-08-30：**L6 token 级流式打字机已交付**（参照 nova-agent 生效，commit c0ce385 + learning/18）——actor 用 llm.stream（**stream 不带 tools** 规避 OpenCode Zen 对 stream+tools 的断连）+ 异常降级 chat(带 tools) 兜底 + RetryProvider.stream 连接级重试 + 模型 JSON 决策解析后 answer 拆段回放 on_token→SSE {"type":"token"} 事件（干净文本）+ 前端打字机（StreamText 单调推进不随 text 重置 + step(final) 不置 done + result 延迟 done + 会话切换重置流式 refs）；curl SSE + Playwright 真实 Chrome 逐字打出验证，218 测试全绿。下一步 = 云部署 + 压测实测容量
- 2026-08-29：模型配置与供应商接入已交付——M4 wiring 修复（create_app 真正传 llm 给 TaskManager，配了 key 才生效，之前永远 mock）+ ModelConfigStore（env>JSON>settings 优先级、脱敏、key 只在服务端 0600）+ /v1/settings/model GET/PUT/presets/test + 控制台「模型」页（预设下拉/保存并生效/测试连接/清除 key）+ 保存热生效（set_llm，新建任务生效）；Anthropic 原生协议（/v1/messages）+ 模型页 CC Switch 风格重构（供应商卡片+模型 chips）+ 自定义供应商多配置（profiles CRUD + 前端「我的供应商」+ 模型目录多模型 + 请求路径展示）；218 测试全绿。下一步 = 云部署 + 压测实测容量
- 2026-08-29：审批进阶已交付（F1.3/F2.4）——TOFU 首用信任（同作用域获批后免 interrupt 直行）+ ApprovalBackend 抽象（Local/Redis 跨节点轮询唤醒 + 信任集共享 + fail-fast）+ ApprovalsView 审批中心（历史台账/集中决策/待审批徽标）；200 测试全绿。下一步 = 云部署 + 压测实测容量
- 2026-08-29：人机协作审批 + 工具权限分级已交付（F1.3/F2.4）——Tool.permission 分级 + 编排层审批门（graph interrupt → awaiting_approval → REST decide → Command(resume)）+ 审批 API + Web 审批卡片 + SSE approval 事件 + 超时自动拒绝；190 测试全绿。下一步 = 云部署 + 压测实测容量
- 2026-08-28：开发线已走完 MCP 客户端 + Skills（FR-2/FR-3）→ 多 Agent 并行（F1.4）→ CLI/OpenAI 兼容 REST API（F9.2/9.3）→ 前端入口闭环，下一步 = 云部署 + 压测实测容量
- 技术栈：Python + LangGraph + FastAPI + Milvus（主选）+ 自研 OpenAI 兼容模型网关（可自托管 vLLM/SGLang）
- 产品形态：本地 Web 优先（预留 CLI/API）
- 沙箱：微虚拟化强隔离（Kata/Firecracker），本地开发 Docker 降级
- 2026-08-31：**Agent 代码工作区 P1**——workspace=真实目录经 registry.task_view(cwd) 注入 agent 工具：read/write/edit/glob/grep/bash（对标 DSH）；read 前置 + edit 版本 CAS 防盲改；write/edit 越界拒绝；bash=Git Bash（每次全新进程/超时/输出上限/FLARE_SHELL 覆盖）；权限 read/write/destructive；default 不注入防越权；257 测试全绿
- 阿里云凭证：后续提供，开发阶段用本地模拟（MinIO 模拟 OSS、本地 Redis/PG/向量库），存储层 Provider 可切换
- 新增需求：面试题驱动开发——全面覆盖高级 Agent 工程师考点（多路召回/GraphRAG/记忆/安全/高并发等），实践+真理并重

## 当前进度
- 阶段 0/1 完成：Git 仓库（已公开 Syotick/flare-agent）+ 文档体系 + 记忆 + M1 设计评审（ADR ×15、模块设计、压测方案）
- **M2 核心闭环完成**：flare_common / agent_runtime(ReAct 图+任务 API：POST 202+SSE 真流式+GET 详情/列表+DELETE 删除) / tools_gateway / model_gateway / **web Console(Vite+React18+Tailwind v4+shadcn(Radix)+lucide，flare 耀斑主题，参考 nova-agent)**；conda env flare-agent；make web-dev / web-build
- **M3a RAG 知识库完成**：services/rag 分层（chunking→embedder→store→pipeline 门面），开发默认 HashEmbedder+SqliteVectorStore（生产换 DashScopeEmbedder+pgvector，协议可插拔）；kb_search 工具注入 Agent 注册表；/v1/kb/documents(POST/GET/DELETE)+/v1/kb/search；TestClient 必须用 with 块（否则后台任务被临时 loop 丢弃）
- **Web UX 修复**：用户不暴露 max_steps/thread_id（内部 MAX_STEPS=8；thread_id 自动：send 同步 created.thread_id、pickTask 沿用会话线程、newChat 清空）；切换会话先清 items 再 SSE 回放防残留。
- **Web 控制台**：KnowledgeBaseView(入库/列表/删除/hybrid检索/RAG评测proxy) + MemoryView(事实CRUD/向量检索/上下文块) + App view 切换 + Sidebar 导航可点 + api.ts KB/Memory 客户端；npm run build → dist(gitignore) 由后端 8000 挂载，访问 http://127.0.0.1:8000/（非 3080）。坑：长 heredoc 写 TSX 会截断污染，分段<100行；noUnusedLocals 删未用导入。
- **M5 云原生代码层**：tenant(头→contextvar→TaskRecord.tenant_id)+task_store(InMemory/Sqlite/Redis,FLARE_TASK_STORE)+PgVectorStore(503守卫)+checkpoint生产AsyncPostgresSaver(长连接)+reconcile双写对账+otel(FLARE_OTEL_ENDPOINT)+infra/Dockerfile+k8s 7清单；learning/05更新。坑：aiosqlite需row_factory=Row；AsyncPostgresSaver.from_conn_string是async CM；_save不复活已删任务；MemorySaver做测试checkpointer。
- **M4 模型网关+沙箱**：OpenAICompatibleProvider（tool_calls 映射+tool_call_id 配对+SSE）+ RetryProvider + build_provider(mock|openai, FLARE_MODEL_NAME)；graph 传 tools；sandbox LocalProcessSandbox/DockerSandbox(503)+sandbox_run 工具+registry 接线+TaskManager.close；test_provider/test_sandbox 17 个；learning/10。坑：test_graph provider 补 tools 参数；step_count=工具执行次数；同步测试用 time.sleep。
- **L6 token 级流式打字机（2026-08-30 交付）**：actor 改 llm.stream 收集决策（stream 不带 tools 规避上游 OpenCode Zen 的 stream+tools 断连）+ 异常降级 chat 兜底 + RetryProvider.stream 连接级重试；JSON 决策内部解析后把 answer 拆段回放 on_token → SSE {"type":"token"} 干净事件；前端 token 实时追加 + StreamText 单调推进 + result 延迟 done + 会话切换重置流式 refs；curl SSE + Playwright 逐字打出验证 + 218 测试全绿；learning/18。
- **M3c RAG 评测**：eval/{metrics(recall@k/precision@k/hit_rate/MRR/NDCG),dataset(内置中文集),runner(多策略对比),ragas(代理判定/LLMJudge fail-fast)} + hybrid(RRF) + rerank + kb.search(strategy) + /v1/kb/eval + demo_eval.py + learning/09。测试 16 个。坑：rrf 首次赋值；E501 CJK 宽2；demo 用独立临时库。
- **learning 三架构文档**：06 功能架构（功能域地图/功能清单带 FR/核心链路/依赖/NFR）；07 业务架构（价值主张/能力地图/流程/业务对象/角色 RBAC/多租户/运营）；08 技术架构（技术栈/LangGraph ReAct 机制/数据架构 dev→prod 演进/集成/部署高可用/安全/权衡）。教学风格"实践+真理"，三层文档互相引用。
- **learning 文档扩展**：04 进阶开发指南（开发部分：分层依赖方向/加工具/加API/接模型/换存储/测试纪律；含"假抽象"警示与开发→生产切换矩阵）；05 生产部署指南（部署部分：阿里云 ACK/OSS/PG(pgvector)/Redis/OTel/多租户/百万并发容量/SLO/回滚，✅实现 vs ⏳M5/M6 标注，含 Dockerfile 示例与上线清单）。配套修复 pyproject packages.find 补 memory*（否则生产的 wheel 缺 memory 包）。
- **M3b Round5 审查修复**：M1 短期对话层真接线——tasks.py _recent_messages 从 checkpointer 取该线程近期 user/assistant 消息传入 build_context(recent=)（注意 checkpoint 是 dict，状态在 channel_values）；graph.actor 同 thread 续聊时把新任务输入追加为 user 消息（判定=已有以该输入结尾的 user 消息）；验证用 checkpoint 最后一条 user 消息而非 echo。M2 mem_recall 相关度排序(_fact_relevance: 整句>分词>2-gram)+封顶 k+2。M3 向量记忆 title=文本前24字符+短id。M4 build_context 事实封顶15。M5 pgvector 同库分表决策。M6 Web 续聊须回传 thread_id。
- **M3a Round4 审查修复**：R1 工具 schema 注入 system 消息（graph._build_tool_schema）——只注册进 registry 不够，真实模型看不到就不会自主调 kb_search；R2 store.add 先 DELETE 旧 chunk 再插（防残留）；R3 DocumentCreate.content max_length=100_000；R4 k=Query(ge=1,le=20) + search 维度校验抛 VECTOR_DIM_MISMATCH(422)；R6 测试暴露 HashEmbedder 字面 n-gram 非语义边界（0.9 vs <0.5）；R7 观察截断 300。
- **M3b 分层记忆完成**：services/memory（短期=LangGraph checkpoint 会话；长期=事实库 facts key->value 按 project_id 隔离，开发 SQLite/生产 PG；向量=复用 rag 协议）；F4.3 上下文工程 context.py（截断/摘要/预算优先级）；mem_set/mem_recall 工具；/v1/memory(facts CRUD/notes/search/context)；TaskManager 任务开始按 task_input 自动注入记忆上下文（graph memory_context）；pytest 52 全绿，ruff/black 干净
- **Web 控制台（M3a/M3b 配套）**：三个工作区（对话 SSE 流式 / 知识库 KnowledgeBaseView / 记忆 MemoryView）；App view 切换；Sidebar 导航可点；api.ts 统一客户端。构建 npm run build→dist(gitignore)，后端 8000 静态托管（非 3080）；dev 用 5173。坑：长 heredoc 写 TSX 截断污染→分段<100行；noUnusedLocals 删未用导入。
- **Web UX 修复**：用户不暴露 max_steps/thread_id（内部 MAX_STEPS=8；thread_id 自动：send 同步 created.thread_id、pickTask 沿用会话线程、newChat 清空）；切换会话先清 items 再 SSE 回放防残留；hash 恢复续线程。
- **M6 生产运营**：metrics.py（纯 Python Prometheus 文本格式，/metrics + HTTP 中间件 + 任务埋点，零依赖）+ slo.py（SLO/错误预算/燃烧速率/多窗口告警 14.4x/36x）+ /v1/ops/slo + error-budget；infra/k8s 08-rules + 09-alertmanager + 10-service-monitor；scripts/loadtest.py（进程内 mock 或 --url，p50/p95/p99 vs SLO，报告+门禁退出码）、release_gate.py（健康+版本+预算）、alert_check.py（在线+离线演练）；learning/12。121 测试全绿。坑：dev SQLite checkpointer 长连接锁文件→本地脚本注入 MemorySaver 别抢锁。
- **文档沉淀**：learning/01–12 齐（12=生产运营 SRE）；docs/README 索引已登记；CHANGELOG 全量 M1–M6+Web+UX；CLAUDE 里程碑现状已同步。
- 代码审查：R1=engineering/03；R2=engineering/04（F1-F4）；R3=engineering/05（Web 前端 L1-L4+问题2/3）
- **功能盘点与竞品对比（2026-08-28）**：docs/product/analysis/01-competitive-comparison.md（已登记 docs/README）——8 功能域盘点 + Grok/Codex/DSH 对比；运维治理/三层记忆/RAG评测/多租户领先；三大差距=MCP+Skills、多 Agent 并行、CLI/REST 接入。
- **MCP 客户端 + Skills（已交付，FR-2/FR-3）**：services/mcp（protocol JSON-RPC 零依赖 + client 双传输 Streamable HTTP/SSE + adapter 工具适配命名空间 mcp__<server>__<tool> + gateway 白名单/认证/审计/幂等注册 + mcp_connect/mcp_list 工具 + testing Fake/真实HTTP）+ services/skills（SKILL.md 技能包 frontmatter 解析 + SkillRegistry 安装/卸载/列表/上下文注入 + skill_list/skill_load）；示例技能 examples/skills/code-review；demo 脚本 scripts/demo_mcp.py/demo_skills.py；learning/13；142 测试全绿。坑：长 heredoc 写代码 \n 会被 JS 转义成真换行（用 chr(10)/拼接）；pyproject packages.find 补 mcp*/skills*；SSE endpoint 相对路径用 urljoin。
- **多 Agent/Subagent 并行（已交付，F1.4）**：services/subagent（SubagentRuntime 子任务=独立 ReAct Agent 实例 + MemorySaver 临时 checkpointer + asyncio.gather 并行 + 独立预算/超时/MAX_ACTIVE=64 护栏 + spawn/await(list shield 超时不打断)/run_subagents/list/close）+ 编排工具 spawn_subagent/await_subagent/list_subagents/run_subagents（并行核心原语，单次上限16 prompt）+ create_app 接线（TaskManager 加 llm/registry 属性）；demo 脚本 scripts/demo_subagent.py；learning/14；152 测试全绿。坑：async def 不能内联表达式。
- **Round 6 审查闭环（MCP 客户端）**：归档 docs/engineering/07-code-review-r6.md。M1 图内 schema 冻结→graph.actor 每轮重建 system 工具清单（mcp_connect 中途注册的新工具同任务可见）+ReAct 图端到端用例；M2 SSE 跨 chunk→_split_sse_events 增量切分（残余保留 buffer）+sse_chunk 分块测试；M3 超时可配→McpServerConfig.timeout→build_transport 透传；M4 register_all(server_name=...)过滤；M5 McpGateway.status() 只读；M6 connect/register 审计；M7 观察限长2000+artifacts；M8 白名单默认关明示。坑：202 要显式 Content-Length:0（否则 httpx 等连接关闭）；SSE 分块写用 handler 的 wfile；flaky 根因=time.time()碰撞→list_facts 加 rowid DESC tie-breaker。竞品文档 v1.1（决策时点快照+已落地+DSH star 改定性）。160 测试全绿，ruff/black 干净。
- **CLI + OpenAI 兼容 REST API（已交付，F9.2/F9.3）**：routes/openai_compat.py（POST /v1/chat/completions 标准 Chat Completions 契约 + stream SSE + /v1/models + OpenAI 风格扁平错误 + FLARE_API_KEY 可选认证，复用 TaskManager）；services/flare_cli（FlareClient httpx 瘦客户端可注入 ASGITransport 测试 + chat/tasks/task/models + console script flare）；Settings 加 api_key；.env.example 补 FLARE_API_KEY/FLARE_URL；pyproject include 加 flare_cli*；learning/15；冒烟端到端打通。坑：HTTPException 会被 FastAPI 包成 {"detail":...}，OpenAI 兼容错误要用自定义异常直接返回 JSONResponse。172 测试全绿，ruff/black 干净。
- **前端入口闭环 + 能力盘点（已交付）**：routes/capabilities.py 只读路由 /v1/capabilities/{tools,skills,skills/{name},mcp,subagent}（可选依赖未装配返回空态，注入式测试不炸）；CapabilitiesView 四页签（工具 JSON-Schema/技能指令+资源/MCP 状态/多 Agent 记录）+ ApiView（OpenAI 兼容 Playground + /v1/models + curl/CLI/SDK 示例）；侧栏死占位项"技能·轨迹·工具"→ 可点「能力」+ 新增「开发者」。治理原则：一个能力 = 一个 REST 端点 + 一个前端视图（死代码治理）。坑：skill_registry 只在默认装配路径创建，能力路由要挂可选依赖；前端 API 统一放 api.ts；tsc strict noUnusedLocals。learning/11 §10。178 测试全绿 + tsc/vite build + 真实服务器冒烟。
- **人机协作审批 + 工具权限分级（已交付，F1.3/F2.4）**：Tool.permission 分级（read/write/destructive，默认 read；echo=read、sandbox_run=destructive）+ ApprovalPolicy（默认 destructive 需审批，FLARE_APPROVAL_REQUIRE_LEVEL 可收紧到 write，extra_tools 白名单）+ 审批门（graph tool_executor 敏感工具执行前 interrupt 挂起 → tasks._execute 两段式流：astream 在 __interrupt__ 后结束 → 登记审批 + awaiting_approval + asyncio.Event 等待 → Command(resume) 同 config 续跑；批准放行/拒绝回灌 APPROVAL_REJECTED/超时自动拒绝 timed_out）+ 审批 API routes/approval.py（GET /v1/approvals ?pending_only + GET {id} + POST {id}/decide，重复决策 409/未知 404）+ SSE approval/approval_decision 事件 + Web ChatView 审批卡片（批准/拒绝按钮+状态回灌）+ Sidebar awaiting_approval 黄点 + mock「沙箱执行」演示触发器。learning/16。坑：interrupt 一次性流（resume 要第二段 astream 同 config）；审批超时安全网 300s；asyncio.Event 单进程（多实例需 Redis，M5 TODO）；真实服务器冒烟用 Python httpx（Windows curl 传 UTF-8 载荷会解码错）；uvicorn 入口 agent_runtime.main:app。190 测试全绿（新增 12 test_approval），ruff/black 干净，tsc/vite build 通过，真实服务器冒烟打通。
- **TOFU + 多实例审批后端 + 审批中心（已交付，F1.3/F2.4 进阶）**：TOFU 首用信任（同作用域=会话线程默认获批一次后免 interrupt 直行，FLARE_APPROVAL_TOFU/TOFU_SCOPE 可调，信任记录 manager 统一门控）；ApprovalBackend 抽象（Local 进程内 asyncio.Event + Redis 多实例共享：请求 hash/待审批 set/有序索引 zset/TOFU 信任 set，跨节点轮询唤醒，FLARE_APPROVAL_BACKEND=redis，连不上 fail-fast 任务优雅 failed）；graph/tasks/routes 全 async + approval_scope 透传；审批中心 ApprovalsView（历史台账 + 待审批 5s 自刷新 + 批准/拒绝 + 决策人/原因）+ Sidebar「审批」导航待审批徽标 + App 8s 轮询。learning/16 补七~十章。坑：后端 decide 不再自动记信任（移到 manager 门控）；写 TSX 内容禁用反引号（会截断外层模板串）。200 测试全绿（新增 10），ruff/black 干净，tsc/vite 通过，冒烟打通（TOFU 同线程免审 + Redis fail-fast）。
- **模型配置与供应商接入（已交付，M4 wiring 修复 + 控制台「模型」页）**：create_app 装配 build_provider（修复永远 mock）；ModelConfigStore env>JSON>settings + 脱敏；GET/PUT/presets/test；热生效 set_llm；ModelSettingsView（CC Switch 风格供应商卡片+模型 chips）+ Sidebar「模型」；Anthropic 原生协议 anthropic_compat.py；learning/17。坑：Settings 属性名 model_provider vs 本地字段 provider（映射表）；store 默认 path 从 settings.model_config_path 取；长中文文档用 Python heredoc 写。
- 下一步：服务器到位后的云部署 + 压测实测容量
- 回归基线：全量 218 测试全绿（test_approval 22 + test_settings_model 13 + test_provider 12 + test_mcp 21 + test_flare_cli 5 + test_capabilities 6）

## 目录速览
- `docs/README.md` — 文档中心（总索引 + 管理规范，**唯一入口**）
- `docs/product/` — 产品与技术参考（调研/需求/架构）
- `docs/engineering/` — 开发与工程规范（开发文档）
- `docs/learning/` — 学习与面试（面试题库）
- `docs/adr/` — 架构决策记录
- `CLAUDE.md` — 详细项目记忆（唯一权威源）

## 待决策
预算/模型供应商（开发先默认 DeepSeek/通义兼容接口 + 多供应商可配）、运维人力。
- 2026-08-31：**前端美化 P1-P3 全交付**——Markdown 渲染（react-markdown+remark-gfm+rehype-highlight，代码块语言标签/复制按钮）、气泡重构（用户渐变微光/助手 markdown+打字机/入场动画/时间戳）、Composer 自动增高+圆形发送钮、ToolCallCard 过渡+呼吸边框、WelcomePanel 动态问候+上浮卡片、思考态阶段文字轮换、markdown-body+hljs 暖色 token 样式；tsc 全过；下一步=agent 执行侧优化
- 2026-08-31(2)：**修复+DSh 仿照**——markdown 流式期间即渲染 + detect:true 无语言代码块自动高亮；侧栏工作区=列表+「添加工作区…」（DSH WorkspacePickFlow 仿照），无工作区直接开目录选择，移除输入名字框
