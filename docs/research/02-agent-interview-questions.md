# Flare Agent · 高级 Agent 工程师面试题库（实践 + 真理）

> 版本：v1.0 ｜ 日期：2026-08-27 ｜ 状态：持续扩充
> 定位：**面试考点全覆盖**。每题给出「真理」（理论要点/答题框架）与「实践」（我们在 Flare Agent 中的落地模块）。
> 使用方式：面试答题 = 讲我们怎么做。背理论不如手上有真项目。
> 关联需求：FR-10（面试考点全覆盖）——本文件是验收清单，每个考点对应一个落地模块或实验。

---

## 1. Agent 核心概念与循环

**Q1. 什么是 Agent？Agent 与 Workflow / Chain / 普通 LLM 应用的区别？**
- 真理：Workflow 是固定编排（DAG，人定义路径）；Agent 是模型自主决策的循环（LLM 决定下一步动作），具备**感知-规划-行动-反思**闭环。关键区别在"决策权在谁手里"。
- 实践：Flare Agent 用 LangGraph 做图式编排，节点可被模型动态选择（Agent 模式）或静态固定（Workflow 模式），二者可混合。

**Q2. Agent 循环由哪几部分构成？**
- 真理：1) 指令/目标 → 2) 规划（拆解步骤）→ 3) 推理（选工具/生成）→ 4) 工具执行 → 5) 结果回填 → 6) 反思/自检 → 循环直至满足终止条件。还要有：上下文管理、记忆读写、预算控制、错误恢复、终止判断。
- 实践：我们的循环 = 规划节点 + 推理节点 + 工具调度 + 反思节点，LangGraph checkpoint 全程持久化。

**Q3. 常见 Agent 范式？ReAct / Plan-and-Execute / Reflection / ToT 各自适用场景？**
- 真理：
  - **ReAct**：推理与行动交替（thought→action→observation），通用、简单、可解释，工具型任务首选。
  - **Plan-and-Execute**：先整体规划再逐步执行，长任务省 token、可恢复，但规划可能过期。
  - **Reflection**：自我批评修正（actor+critic 两轮），适合写作/代码质量。
  - **ToT/GoT**：多路径树/图搜索，适合搜索空间大的推理，成本高。
- 实践：默认 ReAct 循环；长任务切换到 Plan-and-Execute（规划器 + 执行器双节点）；代码任务后置 Reflection 校验节点。

**Q4. 如何防止 Agent 死循环/失控？**
- 真理：硬性步数上限、token/成本预算、超时熔断、循环检测（状态哈希去重）、人工 interrupt 兜底、max iterations + 收敛信号。
- 实践：LangGraph recursion_limit + 自定义预算拦截（步数/成本/时长三者任一超限即中断并通知）。

---

## 2. 编排框架与 LangGraph

**Q5. 为什么选 LangGraph 而不是 LangChain/自研？**
- 真理：LangGraph 是**图式状态机**——状态显式、支持 checkpoint 持久化、interrupt（人机协作）、时间旅行（重放/回滚）、多 Agent 拓扑；相比 LangChain 的 chain 更适合复杂可控的 Agent。
- 实践：选型论证见调研报告 §2；我们在其上加自己的 AgentRuntime 抽象，避免被框架锁死。

**Q6. 长任务中途进程挂了怎么恢复？**
- 真理：把状态（节点进度、中间变量、消息历史）持久化到外部存储（PG/Redis），用 checkpoint 恢复；恢复后从 checkpoint 继续，避免重复执行副作用（幂等）。
- 实践：LangGraph CheckpointSaver 接 PostgreSQL；任务表记录状态机；执行器重试时幂等（任务 ID + outbox）。

**Q7. 什么是 human-in-the-loop / interrupt？怎么实现敏感操作审批？**
- 真理：Agent 执行到敏感动作（执行代码、写文件、外发数据）前暂停，把决策权交给人；批准后从暂停点继续。实现要点：状态先落库、暂停标记、恢复入口、超时策略。
- 实践：LangGraph interrupt 节点 + 审批任务表 + Web 审批按钮；审批记录全量入审计日志。

**Q8. 多 Agent 架构有哪几种？怎么选？**
- 真理：Supervisor（主管分派）、Router（路由分发）、Hierarchical（层级）、Sequential Handoff（接力）、Graph/Network（网状协作）。单 Agent 能解决的别上多 Agent——协调成本高、容易漂移。
- 实践：先单 Agent 打磨；代码任务用 Subagent 并行（Codex 式"多 agent 并行出 PR"）；后续加 Supervisor 做编排层。

---

## 3. 工具调用 / Function Calling / MCP

**Q9. Function Calling 的原理？**
- 真理：模型输出结构化参数（JSON）而非自由文本；通过 JSON Schema 约束；服务端校验参数 → 执行 → 把结果作为新消息回填，模型基于结果继续。要点：工具描述要准确（决定选对率）、参数要严格校验、结果要截断防上下文爆炸。
- 实践：工具定义统一 Schema 注册表；执行前后全链路埋点；返回结果按 token 预算截断。

**Q10. 工具调用失败/格式错误怎么办？**
- 真理：重试 + 错误注入回模型（把异常作为 observation 让模型自愈）、参数校验提前拦截、超时兜底、幂等（避免重复副作用）、防抖。
- 实践：工具调度器带重试策略与幂等键；异常结构化为 observation 回填，模型可改参重试。

**Q11. 什么是 MCP？为什么企业要用 MCP 网关？**
- 真理：MCP 是"AI 应用的 USB-C"——统一工具/资源/提示词协议，Server 一次接入处处复用。企业化必须收敛成**网关**：客户端不直连任意 Server，网关做认证、授权、限流、审计、白名单，防 Prompt 注入放大与越权。
- 实践：自研 ToolRegistry（内置工具）+ MCP 客户端适配器（Streamable HTTP/SSE transport）+ MCP 网关（鉴权/限流/审计）。详见调研 §3。

**Q12. 工具权限分级怎么做？**
- 真理：只读 < 写 < 破坏性/外发；与租户 RBAC 对齐；敏感工具强制审批；执行前资源限额（CPU/内存/时长/网络）。
- 实践：工具元数据带 risk 等级；策略引擎在网关层裁决 allow/deny/require_approval；破坏性工具一律 interrupt。

---

## 4. 记忆与上下文工程

**Q13. Agent 的记忆分几层？**
- 真理：1) 会话短期记忆（窗口内，Redis）→ 2) 项目/任务长期记忆（结构化摘要 + 关键决策，PG）→ 3) 用户/组织级长期记忆（向量记忆，按需检索）。记忆 ≠ 全部塞进上下文，要"按需取用"。
- 实践：分层记忆服务：短期 Redis(TTL) + 中期 PG（项目记忆/决策日志）+ 长期向量记忆（可选）。每层独立读写 API。

**Q14. 上下文窗口不够用怎么办？（上下文工程）**
- 真理：滑动窗口 + 摘要压缩 + 结构化抽取（事实/决策/待办）+ 检索式记忆（只注入相关片段）+ 工具结果精简。压缩时机要触发式（接近窗口阈值），避免过度丢失。
- 实践：ContextManager 组件：token 计量 → 裁剪策略（truncate/summarize/extract）→ 写回记忆；策略可配置可插拔。

**Q15. 向量记忆和 RAG 有什么区别？**
- 真理：RAG 检索**外部知识库**（文档/代码库，来源权威、需溯源）；向量记忆检索**Agent 自己的历史经验**（会话摘要、决策、偏好，无权威来源）。两者技术同源（向量检索），但数据来源、更新频率、可信度标注不同。
- 实践：同一向量检索底座（Milvus），按 Collection 分域：kb_*（知识库，带 citation）与 mem_*（记忆，带时间/来源），检索时隔离。

---

## 5. RAG 全栈（重点）

### 5.1 基础与索引

**Q16. 什么是 RAG？为什么需要？RAG vs 微调 vs 长上下文？**
- 真理：RAG=检索增强生成，解决知识时效、私有知识、幻觉、成本。对比：微调注入风格/领域能力但贵且不更新；长上下文简单但贵、慢、且长文本中模型"迷失在中间"；RAG 快、可溯源、可增量更新——生产首选，三者可组合。
- 实践：RAG 是 Flare Agent 知识库核心（FR-5），全链路带溯源引用。

**Q17. 分块（Chunking）策略怎么选？**
- 真理：定长分块简单但割裂语义；按语义/章节分块（Markdown 标题、PDF 段落）保留结构；父子块（Parent-Child：父块索引、子块召回、父块喂给模型）兼顾召回与上下文；块要重叠防切句；结构化文档保留层级元数据。
- 实践：解析器（PDF/Word/MD/HTML/代码）→ 语义分块 + 元数据；实现 Parent-Child 检索实验（对应面试高频题）。

**Q18. Embedding 模型怎么选？**
- 真理：看维度/检索质量/语言/成本/延迟；中文场景 bge-m3、text-embedding-v3（通义）、gte 等；要建自己的评测集（不是排行榜分数高就好）；输入上限（8192 token 等）；向量维度影响存储成本。
- 实践：EmbeddingProvider 抽象，默认通义/智谱兼容接口，维度与模型版本写入索引元数据，可热切换重索引。

### 5.2 多路召回与检索（面试"多条 RAG"重点）

**Q19. 什么是多路召回（Multi-Route/多路检索）？怎么做？**
- 真理：同时用**多种检索策略**召回再融合，取长补短：1) 向量检索（语义）2) BM25/全文（精确词/专有名词）3) 元数据过滤（时间/类型/权限）4) 多模型 embedding 各一路 5) 多知识库路由。融合用 **RRF（倒数排名融合）** 或加权分数归一。比单路召回召回率更高、更稳。
- 实践：MultiRetriever：route 列表（vector / bm25 / hybrid）+ fusion（RRF/加权）可配置；对应 Q19/Q20/Q21 全链路落地。

**Q20. 混合检索（Hybrid Search）和 RRF 是什么？**
- 真理：混合检索 = 向量 + 关键词（BM25）并行检索。RRF：`score = Σ 1/(k + rank_i)`，k≈60，把多路结果按排名融合，避免跨模态分数不可比。比简单加权稳定。
- 实践：实现 HybridRetriever = VectorRetriever + BM25Retriever（Elasticsearch/内置），RRF 融合，k 可调。

**Q21. 查询改写（Query Rewriting）/ HyDE / Query Routing 是什么？**
- 真理：查询改写：LLM 把模糊问题改清晰/拆多跳；HyDE：先让 LLM 生成假设答案再检索（缓解 query-文档分布漂移，延迟高，可做可选项）；Query Routing：判断该查哪个库/该用哪种检索（分类/嵌入匹配），是 Adaptive/Agentic RAG 的关键。
- 实践：QueryProcessor 组件：改写 → 路由（多知识库/多策略）→ 检索；对应 Adaptive RAG 落地。

**Q22. Rerank（重排）为什么在 RAG 里几乎必做？**
- 真理：向量召回 top-K 里混噪声，cross-encoder 重排（把 query+doc 一起编码打分）精度远超双塔向量；用 Rerank 把 top-50 → top-5，提升上下文精确率。代价是延迟，可并行/缓存。
- 实践：Reranker 抽象（bge-reranker / 通义 rerank / 本地 cross-encoder），检索流水线：recall 50 → rerank 5 → 合成。

### 5.3 高级 RAG

**Q23. GraphRAG 解决什么问题？和传统 RAG 的差别？**
- 真理：传统 RAG 对"跨文档多跳问题/全局性问题"弱（"所有文档里有哪些共同主题？"）。GraphRAG 先抽实体-关系建知识图谱，再社区检测+摘要，能答全局性问题；代价：索引成本高、图谱构建复杂。LightRAG 等做轻量化。
- 实践：预留 GraphRAG 模块（图库可接 Neo4j/内存图）；索引管线按需开启图谱构建；面试演示用"全局性提问 vs 局部性提问"对比。

**Q24. Agentic RAG / Self-RAG / Corrective RAG 是什么？**
- 真理：Agentic RAG：检索→判断是否够→不够再检索/换策略（多轮工具化）；Self-RAG：模型自评"是否需要检索、检索质量、回答忠实度"（反思 token）；Corrective RAG：检索后先评估，不合格就改写查询重试或放弃。本质都是"让检索成为可决策的动作"。
- 实践：RAG 检索节点做成 Agent 工具（可被模型调用多次/判断够不够），评估器（faithfulness/相关度）驱动自省重试。

### 5.4 RAG 评估

**Q25. RAG 怎么评估？RAGAS 指标有哪些？**
- 真理：RAGAS 四大类：**上下文相关性/精确率**（检索到的有没有用）、**上下文召回率**（该召回的有没有漏）、**忠实度 Faithfulness**（回答是否忠于上下文）、**答案相关度**（是否答所问）。离线跑基准集 + 在线埋点（命中/引用/点赞踩）。
- 实践：离线评测脚本（RAGAS + 自建黄金集，进 CI）；在线 RAG 埋点（检索命中、citation 溯源、用户反馈回流）。

**Q26. RAG 效果差一般怎么排查？（性能分析思路）**
- 真理：分层定位：是索引问题（解析/分块/embedding）？检索问题（召回不足/噪声多）？还是生成问题（幻觉/答非所问）？先看"检索到没"再谈"答得好不好"；用评测集量化每层。
- 实践：流水线每段输出都可观测（trace 分 span：parse/chunk/embed/recall/rerank/generate），一键看瓶颈。

---

## 6. 流式与实时交互

**Q27. SSE 和 WebSocket 怎么选？流式输出注意什么？**
- 真理：SSE 单向文本流（服务端→客户端），简单、自动重连，适合 token 流；WebSocket 双向，适合多 Agent 事件+审批交互。注意：背压（客户端慢消费）、心跳/超时、中断取消（省 token）、断线续传。
- 实践：任务事件走 SSE（token/进度/审批请求），交互式审批走 WebSocket 或轮询审批接口；取消机制贯穿。

---

## 7. 模型网关与推理优化

**Q28. 为什么需要模型网关（LLM Gateway）？**
- 真理：统一协议（OpenAI 兼容）、多供应商路由（成本/能力/地域）、灰度与降级（故障切换）、配额与成本核算（租户级）、语义缓存、审计与限流、密钥统一管理。参考 Mockingly LLM Gateway 系统设计题。
- 实践：Gateway 服务（兼容 OpenAI API）：路由策略（优先级/成本/可用性）→ 重试/降级 → 语义缓存 → 配额计量。

**Q29. 推理引擎 vLLM / SGLang / TensorRT-LLM 区别？**
- 真理：vLLM 靠 PagedAttention（KV cache 分页）提吞吐，生态最大、OpenAI 兼容好；SGLang 靠 RadixAttention（前缀树复用）适合多轮/共享前缀、结构化输出；TensorRT-LLM 绑 NVIDIA 极致优化但开发重。生产常用 vLLM + 必要时 SGLang。
- 实践：Gateway 下游可接 vLLM（OpenAI 兼容），自托管推理按需开启（GPU 场景）；对应调研 §6。

**Q30. 推理成本怎么控制？**
- 真理：语义缓存、小模型分流（简单问题用小模型）、模型路由（贵模型只给复杂任务）、token 预算/最大输出限制、上下文压缩、批量离线、流式早停（用户打断）。
- 实践：Gateway 语义缓存 + 路由分级（fast/cheap model for 简单工具调用；strong model for 复杂规划）+ 每租户配额看板。

---

## 8. 高并发与系统设计

**Q31. 怎么设计一个百万级用户的 LLM/Agent 应用架构？（高频系统设计题）**
- 真理：套路：**无状态接入 + 事件驱动 + 有状态外置 + 队列削峰 + 分层缓存 + 弹性伸缩**。
  1) 网关层：认证/限流/路由；2) 应用层：无状态 Pod，HPA 按 CPU/队列深度；3) 会话/状态：Redis/PG 外置，可恢复；4) 长任务：消息队列（Kafka/RocketMQ）削峰，工作线程消费，SSE 推送进度；5) 模型：网关 + 多供应商 + 缓存；6) 存储：读写分离 + 分片。参考 ChatGPT-scale 系统设计题。
- 实践：这是我们的目标架构（docs/architecture/01），M5 用压测（k6/Locust）+ HPA 验证。

**Q32. 限流怎么做？分布式限流要点？**
- 真理：令牌桶/漏桶/滑动窗口/计数器；分布式用 Redis（Lua 原子）+ 本地令牌桶兜底；按租户/用户/模型/接口多维度配额；超限返回 429 + 重试策略；峰值削峰（队列）。参考阿里百炼 RocketMQ LiteTopic 限流。
- 实践：Gateway + 接入层双层限流：Redis 分布式限流（lua）做全局，本地令牌桶做缓冲。

**Q33. 消息队列在 Agent 系统里的作用？幂等怎么保证？**
- 真理：解耦长任务、削峰、任务编排（事件驱动）、故障重试；幂等：消息带唯一 ID + 消费端去重（DB 唯一键）+ outbox 模式保证"本地事务和发消息原子"。At-least-once + 幂等 = 不丢不重。
- 实践：任务事件 outbox + 消费者幂等表；执行器任务 ID 幂等。

---

## 9. 安全、合规与沙箱

**Q34. 什么是 Prompt Injection？怎么防护？（必考）**
- 真理：恶意输入让模型偏离指令/执行越权动作。防护：指令边界（分隔符隔离系统指令与用户输入）、输入/输出过滤（敏感信息/注入模式）、**权限最小化**（工具分级+审批）、工具输出脱敏、沙箱隔离执行、模型侧系统提示加固。参考 2026 面试宝典"Agent 权限过大危害指数级放大"。
- 实践：网关层注入检测 + 工具权限分级 + 审批 + 沙箱执行，四层纵深。

**Q35. 代码执行沙箱怎么做？为什么企业要 Kata/Firecracker？**
- 真理：Docker 共享内核（容器逃逸风险），不可信代码要**微虚拟化**（Kata/Firecracker：每任务独立轻量 VM、独立内核）或 gVisor 用户态内核。要点：网络出口白名单、资源限额（CPU/内存/磁盘/时长）、无 host 挂载、产物走对象存储。对应 Codex 云沙箱。
- 实践：SandboxProvider 可插拔：dev=Docker，prod=Kata/Firecracker；执行超时强杀；产物传 MinIO/OSS。

**Q36. 多租户隔离怎么做？**
- 真理：租户 ID 贯穿所有数据路径（表/Collection/缓存 key 全带 tenant_id）；行级安全 + 服务层强制过滤（防越权必须后端断言）；资源配额隔离（并发/存储/token）；密钥与配置按租户隔离。越权是最严重的安全 bug，要专项测试。
- 实践：中间件自动注入 tenant 上下文；DB 层行级过滤；Milvus 按租户分 Collection/分区；红队越权用例进 CI。

---

## 10. 评测与可观测（LLMOps）

**Q37. LLM/Agent 应用怎么可观测？**
- 真理：OpenTelemetry + GenAI 语义约定（span 里带 model/token/工具调用/检索命中/成本）；一条 Agent 任务=一条 trace；指标（QPS/延迟/token 成本/成功率）+ 结构化日志 + 评测。出问题能复现。
- 实践：全链路 OTel instrumentation（FastAPI + LangGraph + Gateway + RAG 全打点）；Grafana 看板；Langfuse 可选用。

**Q38. Agent 质量怎么评测？（单元级→系统级）**
- 真理：分层：1) 单能力评测（工具选择正确率、检索命中率、格式合规）2) 端到端任务成功率（黄金数据集）3) 在线指标（用户满意、采纳率）+ 影子流量回归 + 生产漂移监控。评测集要持续积累（bad case 回流）。
- 实践：eval/ 目录：黄金集 + RAGAS + 任务成功率；CI 门槛；bad case 回流建回归。

---

## 11. 大厂真题摘录（来源见文末）

- **字节 AI Agent 二面（飞连）**：Function Calling 用 OpenAI 风格 JSON Schema、字段 snake_case 逐个写描述（来源：cloud.tencent.com 字节面经）。
- **字节一面「长短期记忆」**：别只答滑动窗口和向量库——要答分层、写入时机、压缩策略（来源：gitcode 字节一面）。
- **RAG 必问**：embedding 怎么选、分块 trade-off、混合检索/GraphRAG/Rerank、6 个 trade-off（来源：字节阿里百度 RAG 15 题）。
- **系统设计**：设计支持百万级用户的 LLM 应用架构（来源：CSDN LangChain4j 题）；LLM Gateway 系统设计（来源：Mockingly）。
- **Agent 权限**：Agent 权限过大时注入危害指数级放大，需最小权限+人工审批（来源：2026 面试绝杀 160 题）。

---

## 12. 考点 → 项目模块映射表（实践+真理闭环）

| 考点 | 理论(真理) | 落地模块(实践) | 里程碑 |
| --- | --- | --- | --- |
| Agent 循环/范式 | §1 Q1-4 | services/agent-runtime（LangGraph 图：plan→act→reflect） | M2 |
| 长任务恢复/审批 | §2 Q6-7 | checkpoint(PG) + interrupt 审批 | M2 |
| 多 Agent | §2 Q8 | subagent 并行 + supervisor 预留 | M2/M6 |
| Function Calling | §3 Q9-10 | 工具注册表 + 调度器 | M2 |
| MCP 网关 | §3 Q11-12 | mcp-gateway + ToolRegistry | M2/M3 |
| 记忆分层/上下文 | §4 Q13-15 | memory 服务 + ContextManager | M3 |
| 多路召回/混合检索/RRF | §5 Q19-20 | MultiRetriever + HybridRetriever | M3 |
| 查询改写/路由/HyDE | §5 Q21 | QueryProcessor | M3 |
| Rerank | §5 Q22 | Reranker 抽象 | M3 |
| GraphRAG | §5 Q23 | graphrag 模块（预留） | M4 |
| Agentic/Self/Corrective RAG | §5 Q24 | 检索即工具 + 自省评估 | M4 |
| RAG 评估 | §5 Q25-26 | eval/ + RAGAS + 在线埋点 | M3 |
| 流式 | §6 Q27 | SSE/WS + 取消 | M2 |
| 模型网关/推理优化 | §7 Q28-30 | model-gateway + 语义缓存 + 配额 | M4 |
| 百万并发系统设计 | §8 Q31 | 无状态+事件驱动+队列+HPA（架构文档） | M5 |
| 限流/幂等 | §8 Q32-33 | 双层限流 + outbox | M5 |
| 安全/沙箱/租户 | §9 Q34-36 | 注入检测 + SandboxProvider(Kata/Firecracker) + 租户上下文 | M4/M5 |
| 可观测/评测 | §10 Q37-38 | OTel + eval + 看板 | M5 |

> **闭环要求**：上表每个模块写代码时必须：① 理论注释/文档 ② 对应面试题能对着代码讲 ③ 有测试/实验数据。

---

## 13. 参考来源

- [AI Agent 面试真题库 240 题（GitHub）](https://github.com/SuperGODOG/ai-agent-interview-240)
- [AI Agent 面试全攻略 200+ 题（GitHub, 含 RAG/记忆八股）](https://github.com/bcefghj/ai-agent-interview-guide)
- [AgentGuide 面试题库（GitHub）](https://github.com/adongwanai/AgentGuide/blob/main/docs/04-interview/03-agent-questions.md)
- [65 题 AI Agent 全栈开发面试宝典（阿里云）](https://developer.aliyun.com/article/1739618)
- [2026 面试绝杀 OpenClaw + AI Agent 160+ 题（腾讯云）](https://cloud.tencent.cn/developer/article/2654860)
- [RAG Pipeline Design Interview Guide（CalibreOS）](https://www.calibreos.com/blog/genai-rag-pipeline-design-interview-guide)
- [字节阿里百度 RAG 面试 15 题 + 生产避坑](https://gitcode.csdn.net/6a17fe8910ee7a33f2761f72.html)
- [GraphRAG 与 LightRAG 大厂面试题汇总](https://notes.kamacoder.com/interview/llm/graphrag_interview.html)
- [字节一面：Agent 长短期记忆怎么做](https://gitcode.csdn.net/69fb37780a2f6a37c5a819a0.html)
- [字节 AI Agent 二面（飞连）题解](https://cloud.tencent.cn/developer/article/2673729)
- [设计支持百万级用户的 LLM 应用架构（CSDN）](https://blog.csdn.net/qq_43071699/article/details/159431950)
- [LLM Gateway System Design（Mockingly）](https://www.mockingly.ai/questions/llm-gateway-system-design)
- [SSE 流式响应工程实践（CSDN）](https://blog.csdn.net/2301_79289774/article/details/161340066)
- [LangGraph Interrupts 文档](https://docs.langchain.org.cn/oss/python/langgraph/interrupts)
- [阿里云：在 LangGraph 中使用会话状态](https://help.aliyun.com/zh/functioncompute/using-session-state-in-langgraph)
- [Advanced RAG Pipeline（Parent-Child + HyDE + Hybrid + Rerank + RAGAS, GitHub）](https://github.com/siddhantjain603/enterprise-rag)

> 说明：检索完成于 2026-08-27。面试题会随项目推进持续扩充（bad case 回流）。
