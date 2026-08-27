# Flare Agent · 分层记忆与上下文工程（实践 + 真理）

> 版本：v1.0 ｜ 日期：2026-08-27 ｜ 状态：draft
> 定位：M3b 分层记忆（FR-4）配套教学文档：会话短期 -> 项目长期事实 -> 向量记忆 + F4.3 上下文工程。
> 关联需求：FR-4（会话、项目与记忆）、FR-10（面试考点）。

---

## 1. 为什么 Agent 需要记忆

- 真理：LLM 无状态（每次调用独立）。Agent 想跨会话记住用户偏好、项目约定、历史决策，
  必须把状态放在**外部存储**，并在每次调用前把相关内容**注入上下文**。
  记忆设计三问：存什么（事实/对话/笔记）、存多久（短期/长期）、怎么取（精确键 / 语义召回）。
- 实践：Flare Agent 把记忆做成 Agent 的**工具（mem_set/mem_recall）+ 上下文自动注入**双通道：
  - 显式：模型可主动调用 mem_set 记住、mem_recall 回忆；
  - 隐式：任务开始前按 task_input 自动召回记忆并注入首个 user 消息（无需模型主动想起）。

## 2. 分层记忆（FR-4.2）

- 真理：按「生命周期 + 存储介质」分层，成本与时效匹配：
  - **短期**：会话内消息（Redis / checkpoint）——快、过期即弃；
  - **项目长期**：关键事实 key-value（PG）——跨会话、精确读写；
  - **用户/组织级**：向量记忆（向量库）——语义召回，回答"凭感觉记得的"。
- 实践（services/memory/）：
  - 短期 = LangGraph checkpointer 按 thread_id 持久化消息（M2 已有）；
  - 长期 = MemoryManager 事实库（facts 表，key->value，按 project_id 隔离；开发 SQLite / 生产 PG 同结构）；
  - 向量 = 复用 rag 的 Embedder/VectorStore 协议，笔记以 document 形式入库做语义召回。

## 3. 上下文工程（F4.3）

- 真理：上下文预算有限（token/字符）。注入要「截断 + 摘要 + 优先级」：
  事实最值得（精确）、向量次之（相关）、对话最后（重复信息多）；
  超预算时宁可丢近期对话，也要保住事实。
- 实践（memory/context.py）：assemble() 把三层拼成块，逐项 summarize()（句子边界摘要），
  超预算先丢对话再硬截断。开发版摘要为确定性截断，生产可换 LLM 摘要（model_gateway）。

## 4. 注入时机

- 真理：上下文注入的时机 = 任务开始时（per-turn 注入会重复烧 token）。
  注入内容应与当前任务相关（按任务输入做向量召回），而不是全量倾倒记忆。
- 实践：TaskManager._execute 里，任务开始前调 memory.build_context(query=task_input)，
  把上下文块作为首个 user 消息的前缀注入（graph.actor 的 memory_context 参数）。

## 5. 工程要点与踩坑

- **事件循环**（同 M3a）：SQLite/aiosqlite 连接绑定创建它的 loop。
  TestClient 必须用 with 块保持单一 portal loop；跨 worker 共享记忆是 M5 迁 PG/Redis 的动因。
- **写文件转义**：脚本/文档里的 Python 字符串若含换行转义，注意模板字面量的反斜杠 n 会被求值为真换行；
  用 chr(10) 或纯 print() 分隔更稳。
- **分层取舍**：mem_recall 先列长期事实（全量，量小）再列向量命中（按 query）；
  事实库过大时（M5）再做"按前缀/最近"分页。

## 6. 验收

- [ ] PUT/GET/DELETE /v1/memory/facts 事实 CRUD（按 project_id 隔离）
- [ ] POST /v1/memory/notes + /v1/memory/search 向量记忆召回
- [ ] GET /v1/memory/context 返回三层上下文块（带预算截断）
- [ ] Agent 任务开始时自动注入记忆上下文（tests/test_memory.py::test_memory_context_injected_into_task）
- [ ] pytest 全绿（52 passed）
- 下一步：M3c RAG 评测（RAGAS）+ 混合检索/重排；把记忆/知识库管理页接进 Web 控制台。
