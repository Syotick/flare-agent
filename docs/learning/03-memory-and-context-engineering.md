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
    **三层真正接线（M1）**：TaskManager 任务开始时从 checkpointer 取该线程近期 user/assistant
    消息传入 build_context(recent=...)，[近期对话] 会注入上下文；续聊 = Web 复用同一 thread_id。
  - 长期 = MemoryManager 事实库（facts 表，key->value，按 project_id 隔离；开发 SQLite / 生产 PG 同结构）；
    进上下文时按最新 15 条封顶（M4：事实内部预算分级，M5 换 LLM 摘要）。
  - 向量 = 复用 rag 的 Embedder/VectorStore 协议，笔记以 document 形式入库做语义召回；
    溯源可读（M3）：title = 笔记文本前 24 字符 + 短 id（如「部署在阿里云 ACK 集群·3f9a2b」），
    不再是 memory:<nid>。

## 3. 上下文工程（F4.3）

- 真理：上下文预算有限（token/字符）。注入要「截断 + 摘要 + 优先级」：
  事实最值得（精确）、向量次之（相关）、对话最后（重复信息多）；
  超预算时宁可丢近期对话，也要保住事实。
- 实践（memory/context.py）：assemble() 把三层拼成块，逐项 summarize()（句子边界摘要），
  超预算先丢对话再硬截断。开发版摘要为确定性截断，生产可换 LLM 摘要（model_gateway）。
- **工具侧同样遵守预算（M2）**：mem_recall 不再全量倾倒项目事实——按与 query 的字面相关度
  （整句 > 分词 > 2-gram）排序 + 封顶 k+2 条，无重合时按最近时间兜底；向量命中照旧按 query 召回。

## 4. 注入时机

- 真理：上下文注入的时机 = 任务开始时（per-turn 注入会重复烧 token）。
  注入内容应与当前任务相关（按任务输入做向量召回），而不是全量倾倒记忆。
- 实践：TaskManager._execute 里，任务开始前调 memory.build_context(query=task_input, recent=该线程近期对话)，
  把上下文块作为 user 消息的前缀注入（graph.actor 的 memory_context 参数）。
  **续聊（M1）**：同一 thread 复用 = 图形 resume，actor 会把新任务输入作为新 user 消息追加
  （判定标准：是否已有以本任务输入结尾的 user 消息），短期对话层随之参与上下文工程。

## 5. 工程要点与踩坑

- **事件循环**（同 M3a）：SQLite/aiosqlite 连接绑定创建它的 loop。
  TestClient 必须用 with 块保持单一 portal loop；跨 worker 共享记忆是 M5 迁 PG/Redis 的动因。
- **写文件转义**：脚本/文档里的 Python 字符串若含换行转义，注意模板字面量的反斜杠 n 会被求值为真换行；
  用 chr(10) 或纯 print() 分隔更稳。
- **分层取舍（M2/M4）**：mem_recall 按相关度排序 + 封顶 k+2 条；build_context 事实按最新 15 条封顶。
  事实库过大时（M5）再做"按前缀/最近"分页，并把确定性摘要换成 LLM 摘要。
- **M5 演进决策（提前定）**：kb 与 memory 两个向量库走同一 VectorStore 协议 + 同一 chunk schema
  （doc_id/chunk_index/text/vector）——迁 pgvector 时建议**同一 PG 实例、分表**（kb_chunks / memory_chunks），
  只换 store 实现类，上层零改动；不要在应用层分两个协议实现。
- **thread_id 语义（M6 提醒）**：Web 若要"同一会话续聊"，必须把首个任务返回的 thread_id 原样带回
  （POST /v1/tasks 已支持 thread_id 字段）；新 thread_id = 全新会话。短期对话层只在 thread 内生效。
- **checkpoint 自定义类型**：LLMMessage/ToolResult 走 msgpack 序列化时 LangGraph 提示
  "unregistered type"——开发可用，M5 上生产前需注册 allowed_msgpack_modules 或改用内置消息类型。

## 6. 验收

- [ ] PUT/GET/DELETE /v1/memory/facts 事实 CRUD（按 project_id 隔离）
- [ ] POST /v1/memory/notes + /v1/memory/search 向量记忆召回（溯源可读：文本前缀+短id，M3）
- [ ] GET /v1/memory/context 返回三层上下文块（带预算截断）
- [ ] Agent 任务开始时自动注入记忆上下文（tests/test_memory.py::test_memory_context_injected_into_task）
- [ ] 短期对话层真正接线：同 thread 续聊注入 [近期对话]（test_recent_layer_injected_on_resumed_thread，M1）
- [ ] mem_recall 按相关度排序 + 封顶，不再全量倾倒（test_mem_recall_is_budgeted，M2）
- [ ] pytest 全绿（60 passed）
- 下一步：M3c RAG 评测（RAGAS）+ 混合检索/重排；把记忆/知识库管理页接进 Web 控制台。
