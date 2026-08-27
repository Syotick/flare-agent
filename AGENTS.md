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
- **M3a RAG 知识库完成**：services/rag 分层（chunking→embedder→store→pipeline 门面），开发默认 HashEmbedder+SqliteVectorStore（生产换 DashScopeEmbedder+pgvector，协议可插拔）；kb_search 工具注入 Agent 注册表；/v1/kb/documents(POST/GET/DELETE)+/v1/kb/search；TestClient 必须用 with 块（否则后台任务被临时 loop 丢弃）
- **Web UX 修复**：用户不暴露 max_steps/thread_id（内部 MAX_STEPS=8；thread_id 自动：send 同步 created.thread_id、pickTask 沿用会话线程、newChat 清空）；切换会话先清 items 再 SSE 回放防残留。
- **Web 控制台**：KnowledgeBaseView(入库/列表/删除/hybrid检索/RAG评测proxy) + MemoryView(事实CRUD/向量检索/上下文块) + App view 切换 + Sidebar 导航可点 + api.ts KB/Memory 客户端；npm run build → dist(gitignore) 由后端 8000 挂载，访问 http://127.0.0.1:8000/（非 3080）。坑：长 heredoc 写 TSX 会截断污染，分段<100行；noUnusedLocals 删未用导入。
- **M5 云原生代码层**：tenant(头→contextvar→TaskRecord.tenant_id)+task_store(InMemory/Sqlite/Redis,FLARE_TASK_STORE)+PgVectorStore(503守卫)+checkpoint生产AsyncPostgresSaver(长连接)+reconcile双写对账+otel(FLARE_OTEL_ENDPOINT)+infra/Dockerfile+k8s 7清单；learning/05更新。坑：aiosqlite需row_factory=Row；AsyncPostgresSaver.from_conn_string是async CM；_save不复活已删任务；MemorySaver做测试checkpointer。
- **M4 模型网关+沙箱**：OpenAICompatibleProvider（tool_calls 映射+tool_call_id 配对+SSE）+ RetryProvider + build_provider(mock|openai, FLARE_MODEL_NAME)；graph 传 tools；sandbox LocalProcessSandbox/DockerSandbox(503)+sandbox_run 工具+registry 接线+TaskManager.close；test_provider/test_sandbox 17 个；learning/10。坑：test_graph provider 补 tools 参数；step_count=工具执行次数；同步测试用 time.sleep。
- **M3c RAG 评测**：eval/{metrics(recall@k/precision@k/hit_rate/MRR/NDCG),dataset(内置中文集),runner(多策略对比),ragas(代理判定/LLMJudge fail-fast)} + hybrid(RRF) + rerank + kb.search(strategy) + /v1/kb/eval + demo_eval.py + learning/09。测试 16 个。坑：rrf 首次赋值；E501 CJK 宽2；demo 用独立临时库。
- **learning 三架构文档**：06 功能架构（功能域地图/功能清单带 FR/核心链路/依赖/NFR）；07 业务架构（价值主张/能力地图/流程/业务对象/角色 RBAC/多租户/运营）；08 技术架构（技术栈/LangGraph ReAct 机制/数据架构 dev→prod 演进/集成/部署高可用/安全/权衡）。教学风格"实践+真理"，三层文档互相引用。
- **learning 文档扩展**：04 进阶开发指南（开发部分：分层依赖方向/加工具/加API/接模型/换存储/测试纪律；含"假抽象"警示与开发→生产切换矩阵）；05 生产部署指南（部署部分：阿里云 ACK/OSS/PG(pgvector)/Redis/OTel/多租户/百万并发容量/SLO/回滚，✅实现 vs ⏳M5/M6 标注，含 Dockerfile 示例与上线清单）。配套修复 pyproject packages.find 补 memory*（否则生产的 wheel 缺 memory 包）。
- **M3b Round5 审查修复**：M1 短期对话层真接线——tasks.py _recent_messages 从 checkpointer 取该线程近期 user/assistant 消息传入 build_context(recent=)（注意 checkpoint 是 dict，状态在 channel_values）；graph.actor 同 thread 续聊时把新任务输入追加为 user 消息（判定=已有以该输入结尾的 user 消息）；验证用 checkpoint 最后一条 user 消息而非 echo。M2 mem_recall 相关度排序(_fact_relevance: 整句>分词>2-gram)+封顶 k+2。M3 向量记忆 title=文本前24字符+短id。M4 build_context 事实封顶15。M5 pgvector 同库分表决策。M6 Web 续聊须回传 thread_id。
- **M3a Round4 审查修复**：R1 工具 schema 注入 system 消息（graph._build_tool_schema）——只注册进 registry 不够，真实模型看不到就不会自主调 kb_search；R2 store.add 先 DELETE 旧 chunk 再插（防残留）；R3 DocumentCreate.content max_length=100_000；R4 k=Query(ge=1,le=20) + search 维度校验抛 VECTOR_DIM_MISMATCH(422)；R6 测试暴露 HashEmbedder 字面 n-gram 非语义边界（0.9 vs <0.5）；R7 观察截断 300。
- **M3b 分层记忆完成**：services/memory（短期=LangGraph checkpoint 会话；长期=事实库 facts key->value 按 project_id 隔离，开发 SQLite/生产 PG；向量=复用 rag 协议）；F4.3 上下文工程 context.py（截断/摘要/预算优先级）；mem_set/mem_recall 工具；/v1/memory(facts CRUD/notes/search/context)；TaskManager 任务开始按 task_input 自动注入记忆上下文（graph memory_context）；pytest 52 全绿，ruff/black 干净
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
