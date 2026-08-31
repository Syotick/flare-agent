# 00 · 大厂 Agent 开发岗 JD 与面试题调研（2026-08 实查）

> 状态：draft ｜ 日期：2026-08-31 ｜ 性质：网络实际检索整理（岗位 JD + 面试题库对照）
> 面向：准备投 **AI Agent 开发工程师 / 大模型应用工程师 / Agent 平台工程师** 的读者。

---

## 0. 一句话结论

大厂 Agent 开发岗 = **后端工程能力（50%）+ Agent 核心技术（30%）+ 模型理解/可观测性（20%）**。它本质就是后端平台岗，但多了「Agent 系统设计」和「Eval 评测」两块硬货。中间件（Redis/MQ/Nginx/K8s/向量库）在 JD 里是**明确写进任职要求的**，不是可选项。

## 1. 大厂 JD 拆解（基于真实 JD 全文）

以下提炼自真实岗位 JD（AI Native 方向全文 + 字节/腾讯/美团/百度类目 + 面试库标注的「基于真实 JD 核心考察点」）。

### 任职要求五层

| 层 | 要求 | JD 原文关键词 |
| --- | --- | --- |
| L1 编程与后端基础 | **精通 Python** + 至少一门后端语言（Java/Go/Node/Rust）；可维护/可测试/可观测代码 | 数据结构、算法、**并发与异步**、分布式基础（CAP、一致性）、**数据库**（关系型+NoSQL+**向量库**）、**消息中间件**（Kafka/RabbitMQ/Redis Stream）、**API 网关**、**微服务**、CI/CD、**Docker/K8s**、监控告警、灰度发布 |
| L2 Agent 核心技术 | LLM 原理、Agent 设计模式、**Function Calling**；至少一个框架（LangChain/LangGraph/LlamaIndex/AutoGen/CrewAI/…）；**生产级 Agent** | Agent Runtime、任务规划、上下文管理、工具调用、记忆系统、**人机协同（审批）**、异常恢复、权限治理；单/Multi/Hierarchical Agent 选型；MCP/A2A |
| L3 RAG 与知识工程 | **RAG 端到端**开发经验 | Embedding 选型、**Chunking**、**Hybrid Search**、**Reranker**、GraphRAG；至少一种向量库（Milvus/Qdrant/Weaviate/pgvector/Chroma） |
| L4 Prompt 与评测 | Prompt 是**系统工程**；**Eval 与开发同步建** | CoT/ReAct/Self-Consistency/Reflexion；Ragas/DeepEval/Langfuse/LangSmith；任务完成率、Faithfulness、上下文相关性、工具调用成功率、人工介入率 |
| L5 模型与多模态 | 多模型选型/Routing/降级；多模态（VLM/ASR/TTS）了解；微调是加分（SFT/LoRA/DPO/RLHF） | GPT/Claude/Gemini/Qwen/DeepSeek/Llama；Token 经济、缓存、限流、降级、重试、长上下文优化 |

> 综合素质（JD 原文强调）：韧性（模型不听话是常态）、跨团队协作、Owner 意识、学习速度、工程审美。

## 2. 面试题全景（题库实测）

### 主流题库规模（cdavid817/agent-interview：1798 题）

| 领域 | 题数 | 说明 |
| --- | ---: | --- |
| Agent 核心架构 | 92 | 从 0 到 1 设计企业级 Agent、模块拆分、Runtime/Harness、框架选型（DeepSeek/腾讯/豆包真题） |
| Transformer | 60 | 输入是什么、QKV、注意力复杂度优化（百度 Agent 真题） |
| 任务规划与执行 | 299 | 任务识别、拆解、路由、ReAct/CoT |
| 上下文与知识系统 | 197 | 长对话、Memory、上下文工程 |
| 工具 / Skills / MCP | 221 | Tool Design、Function Calling、MCP 协议 |
| 多 Agent 与协作 | 38 | Multi-Agent 架构、A2A |
| RAG | 197 | 混合检索、评测、增量索引 |
| 模型能力与成本 | 123 | 选型、成本优化、Token 经济 |
| 安全、治理与可观测性 | 159 | 权限、审计、Trace、幻觉 |
| 工程落地与平台化 | 197 | **Coding Agent、代码检索、沙箱、平台工程** |

### 开发岗专项（AgentGuide/06：系统设计 15 + 工程实践 12 + 框架选型 10 + 业务落地 8）

**系统设计高频题（面试重点）**：
- 设计日均百万查询的企业级 RAG（峰值 QPS 3000、P99<500ms、99.9%）
- 设计 Multi-Agent 协作系统（客服：订单/物流/售后 + Supervisor）
- 设计 LLM Gateway（多供应商、限流熔断、成本统计、缓存）
- 设计 Agent 工作流引擎（类 LangGraph：有向图、状态持久化、条件分支、重试）
- 设计分布式 Agent 调度（负载均衡、任务队列、容错）
- 设计 Memory 管理系统（短期/长期、向量检索、遗忘机制）
- 设计 Agent 评估平台、多租户 RAG SaaS、Agent 可观测性系统

**工程实践高频题**：
- 如何把 RAG P99 延迟从 2s 降到 300ms（字节真题）
- 如何降低 API 成本 70%（语义缓存、Prompt 压缩、智能降级、批处理）
- 长对话（>10 轮）怎么处理（压缩、滑动窗口、摘要）
- Agent 异常重试（指数退避、幂等、降级）
- 并发控制（任务队列、限流、资源池、死锁避免）
- 流式处理（SSE/WebSocket、背压、错误恢复）
- 跨模型统一 API（适配器、参数映射、错误码统一）
- 状态持久化（序列化、Redis/Mongo、断点续传）

**框架选型高频题**：LangChain vs LlamaIndex vs AutoGen；LangGraph vs CrewAI vs AutoGen；向量库选型；Memory 框架（Mem0/Zep）；监控（Prometheus+Grafana vs LangSmith vs LangFuse）。

**业务落地高频题**：如何证明 Agent 比人工好（评估方案）、灰度发布、A/B、幻觉治理、**权限控制（RBAC+白名单+审批+审计）**、隐私、ROI。

### 开发岗高频真题 Top 10

1. 设计日均百万级 RAG 系统（必考）
2. 如何优化 P99 延迟（必考）
3. LangChain vs AutoGen 选型
4. 如何降低 API 成本 70%
5. Multi-Agent 架构设计
6. Memory 系统如何实现（Mem0/Zep）
7. 如何评估 Agent 效果
8. 分布式 Agent 的并发控制
9. 异常处理与重试机制
10. 监控与可观测性怎么做

### Coding Agent 专项（与他做的「DSH 型代码 Agent」最相关）

- 几十万行代码的仓库，Coding Agent 怎么快速定位上下文（结构化索引 + 混合检索 + 调用图 + 渐进式上下文）
- 为什么不能整库加载（窗口、注意力稀释/Lost-in-the-Middle、成本、安全、版本一致性）
- 如何建仓库索引（文本+符号+AST+语义+关系，RRF 融合，Git Diff 增量更新）
- 多租户企业级 Agent 平台的数据/权限/资源隔离完整方案

## 3. 对照表：Flare Agent 项目能当答案的题 vs 需要补的

### ✅ 你的项目能直接当答案（面试讲这些）

| 面试题 | 你项目的对应实现 |
| --- | --- |
| 设计 Agent Runtime / Harness | FastAPI + LangGraph 编排 + TaskManager + SSE 实时流 |
| 工具系统怎么设计 | ToolRegistry（名称/描述/JSON Schema/异步函数）+ 权限分级（read<write<destructive） |
| Function Calling / 工具编排 | 六工具（read/write/edit/glob/grep/bash）绑定工作区 cwd |
| 人机协同 / 审批 | LangGraph interrupt 审批门 + TOFU + 三种权限模式（只读/批准/无限制） |
| 权限控制 | 越界拒绝（OUT_OF_BOUNDS）、write 前置 read、edit 版本 CAS、审批白名单 |
| 工作区 / 沙箱隔离 | 工作区=真实目录 + 本地子进程沙箱 + 工具过滤 |
| 跨模型统一 API | model_gateway（mock/openai/anthropic + 重试 + 回退） |
| 状态持久化 / 断点续跑 | task_store（memory/sqlite/redis）+ LangGraph checkpointer + checkpoint.py |
| 流式处理 | SSE 事件流（token/step/approval/result） |
| Memory 系统 | 分层记忆（长期事实+向量+会话上下文），自动召回注入 |
| RAG 端到端 | 入库→混合检索（向量+BM25+RRF）→Rerank→带溯源，RAGAS 评测 |
| 可观测性 | /metrics + SLO 错误预算 + OTel + 结构化日志 |
| 框架选型题（LangGraph vs 其他） | 你真实用过 LangGraph 的 interrupt/checkpoint，能讲取舍 |
| Coding Agent 检索 | 你的 read/glob/grep 就是渐进式上下文的雏形（能往 Repo Map/符号索引方向讲） |

### ⚠️ 面试必考但你项目还没覆盖的（最需要补的）

| 缺口 | 为什么重要 | 怎么补（低成本） |
| --- | --- | --- |
| **Eval 评测体系** | JD 明确要求、Top10 必考 | 给项目加一个 eval 模块（任务完成率/工具成功率指标），能讲 Ragas/DeepEval 概念即可 |
| **高并发/系统设计** | 百万 QPS RAG、分布式调度 | 背熟 06 的 15 道系统设计题框架（检索优化/缓存/并行） |
| **成本优化** | API 成本降 70% 必考 | 理解语义缓存、Prompt 压缩、模型降级（能给项目算 token 账） |
| **中间件实操** | JD 明确写 Redis/MQ/向量库 | Redis 已支持（task_store=redis）；补 K8s/Docker 概念、MQ 概念 |
| **框架横向对比** | LangChain/LangGraph/AutoGen/CrewAI 选型 | 只背各自定位一句话 + 为什么选 LangGraph（interrupt/checkpoint） |
| **Transformer 八股** | 百度/腾讯常问 | 核心 100 题的 TRANS-001~008 过一遍概念 |
| **Multi-Agent 设计** | 高频系统设计 | 你项目有 subagent，能讲 Supervisor 模式 + 状态管理 + 结果聚合 |
| **多模态** | JD 提及（加分） | 了解 VLM/ASR/TTS 能力边界，能说接入方式即可 |

## 4. 行动清单（按优先级，2–4 周）

1. **把自己项目讲成「生产级 Agent 平台」**：架构图 + 3 个设计决策（LangGraph 审批、工作区真实目录、读前置保护）+ 1 个踩坑。这是你最硬的优势。
2. **补 Eval**：给项目加一个简单的评测模块（哪怕 30 行），面试讲「我建了任务完成率/工具调用成功率指标」。
3. **背熟系统设计框架**：AgentGuide 06 的 15 道系统设计题，每道记「架构图 + 3 个要点」，能画出来。
4. **补中间件概念**：Redis（已用）/ MQ / Nginx / Docker-K8s / 向量库，各半天，能说「解决什么问题、放哪层」。
5. **过一遍八股**：Transformer 基础（注意力/QKV/位置编码）+ 幻觉治理 + 权限模型（RBAC）。
6. **投递定位**：优先投「Agent 应用/LLM 应用/Agent 平台」岗；JD 写「熟悉 Redis/MQ/K8s」的，先补实操再投。

## 5. 参考来源

- 面试题库（1798 题）：[cdavid817/agent-interview](https://github.com/cdavid817/agent-interview)（核心 100 题见其 docs/00-guide/core-100.md）
- 开发岗专项题库：[zgd716/AgentGuide](https://github.com/zgd716/AgentGuide) docs/04-interview/06-development-specialized.md
- LLM/VLM/Agent 八股合集：[datawhalechina/hello-agents](https://github.com/datawhalechina/hello-agents) Extra01
- 大厂 JD（AI Native 方向全文）：[天津小橙集团 AI Agent 开发工程师](https://career.nankai.edu.cn/correcruit/content/id/116181.html)
- 大厂岗位页：字节跳动（jobs.bytedance.com）、腾讯（careers.tencent.com）、美团（zhaopin.meituan.com）、OpenAI Codex Agents（openai.com/careers）、Apple Agentic AI