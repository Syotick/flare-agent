# Flare Agent · 技术架构（实践 + 真理）

> 版本：v1.0 ｜ 日期：2026-08-27 ｜ 状态：draft
> 定位：回答"用什么实现、怎么组织、怎么部署、怎么扛住并发"。技术架构是业务/功能架构的实现视图。
> 配套：06-功能架构、07-业务架构；部署细节见 [05-production-deployment-guide](./05-production-deployment-guide.md)。

---

## 1. 技术选型（为什么是这一套）

- 真理：选型三问——生态成熟吗、团队熟吗、和既有架构合吗。没有绝对"最强"，只有"最合"。
- Flare Agent 栈（开发→生产一致演进）：
  - 语言/框架：Python 3.12 + FastAPI（异步、生态全、AI 首选）；
  - Agent 编排：LangGraph（显式图 + 检查点 + 可观测，对比裸 ReAct 的循环靠手写）；
  - 工具层：自研 ToolRegistry（JSON Schema 校验 + 结构化失败观察）；
  - 存储：SQLite（dev）→ PostgreSQL + pgvector（prod，同协议换实现）；Redis（任务/缓存，M5）；
  - 向量：dev HashEmbedder + SqliteVectorStore → prod DashScope text-embedding-v3 + PgVectorStore；
  - 对象存储：OSS（FLARE_OBJECT_STORE_* 已预留，本地 MinIO 模拟）；
  - 前端：React + Tailwind v4 + shadcn(Radix) + lucide（flare 主题）；
  - 可观测：结构化日志（已有）+ OTel → SLS/ARMS/Prometheus（M5）；
  - 部署：uvicorn + 多副本容器（ACK，M5）。

## 2. 分层与依赖方向（模块级）

    flare_common（错误契约/配置/日志）
        ^  ^  ^
        |  |  +---> rag（chunking → embedder → store → pipeline）
        |  +------> memory（事实库 + 向量记忆 + 上下文工程）
        +---------> model_gateway（ModelProvider 协议 + mock）
                     tools_gateway（Tool/Registry）
        agent_runtime（graph + tasks + routes）── 依赖上面全部
        sandbox（M4）· web（独立前端）

- 规则：上层可依赖下层，下层绝不依赖上层；新增包要进 pyproject packages.find（踩坑：memory* 曾漏）。
- 依赖注入：create_app(settings, task_manager, knowledge_base, memory) 让"组装"与"实现"分离——
  测试注入内存实现，生产注入真实底座，main.py 只负责组装。

## 3. 核心运行机制（Agent 是怎么跑的）

- 真理：Agent = 循环：想（思考决策）→ 做（执行工具）→ 看（观察结果）→ 再想，直到收尾。
  循环必须显式化（图/状态机），否则无法预算、无法断点、无法观测。
- LangGraph ReAct 图（services/agent_runtime/graph.py）：
  - actor：注入 system（工具 schema）+ user（记忆上下文 + 输入）→ 模型决策（call_tool/final）；
  - tool_executor：执行 registry 里的工具 → 结构化观察回灌（成功/UNKNOWN_TOOL/INVALID_ARGS）；
  - 预算熔断：step_count > max_steps 强制收尾，且最后一次工具观察后模型仍有收尾机会（F2 修复）；
  - 检查点：BaseCheckpointSaver 按 thread_id 持久化状态（dev SQLite / prod AsyncPostgresSaver）；
  - 坏决策显式化：非 JSON / 半熟 call_tool → INVALID_MODEL_OUTPUT 观察回灌，不静默当答案（F3）。
- 任务层（tasks.py）：POST 立即返回 task_id，后台 asyncio 执行，SSE 实时推事件（L1 真·流式）。

## 4. 数据架构（开发 → 生产演进）

- 真理：数据分三类——冷（源文档/历史，存 OSS）、热（会话/任务，存 Redis/内存）、
  准（向量/事实/检查点，存 PG）。按访问频率选介质，别把一切塞一个库。
- 现状（dev）：
  - data/kb.sqlite3（知识库 chunk：doc_id/chunk_index/text/vector）；
  - data/memory.sqlite3（事实：project_id/key/value/updated_at）；
  - data/memory_vec.sqlite3（向量记忆，同 chunk schema）；
  - data/flare_agent.sqlite3（LangGraph checkpoint）。
- 演进（M5）：同一 VectorStore 协议 → PG 同库分表 kb_chunks / memory_chunks；
  facts 同结构上 PG；checkpoint → AsyncPostgresSaver；任务/事件 → Redis；源文档 → OSS。
- 关键约束（教训）：aiosqlite 连接绑定创建它的 loop，不能跨 loop 共享（TestClient 必须 with 块）；
  迁移时先双写对账再灰度（learning/05 §4）。

## 5. 集成架构（外部世界怎么接进来）

- 模型网关：ModelProvider 协议（chat/stream）——mock 供应商（开发）→ 真实模型（M4，
  function-calling 映射 _parse_decision）；API Key 走 Secret，成本走 max_steps 预算护栏。
- 工具注册：ToolRegistry 统一执行 + JSON Schema 校验；工具 schema 首轮注入 system 消息（R1）
  ——模型"看得见"才能自主调用，这是 Agent 化 RAG 的前提。
- 对象存储：OSS SDK 走 FLARE_OBJECT_STORE_*（本地 MinIO 模拟），存源文档/多模态/产物。
- 可观测：OTel 三信号（日志已有结构化；trace/span 包住 请求→Agent 轮次→工具→LLM，M5 导出）。

## 6. 部署与高可用

- 真理：高可用 = 无状态应用 + 有状态底座托管 + 水平扩展 + 可回滚。应用层绝不落本地盘。
- 拓扑：ALB/Nginx → ACK 多副本（HPA）→ PG/Redis/OSS（云托管）；/health 探针；滚动更新 + 金丝雀。
- 并发模型（百万级目标）：每副本 QPS x 副本数 >= 峰值且留 50% 余量；瓶颈顺序
  模型网关 > PG 连接池 > Redis 吞吐；用连接池 + 限流 + 结果缓存解掉（learning/05 §7）。
- 现状：单进程 uvicorn + SQLite（dev）✅；容器/K8s/OTel 为 M5 ⏳。

## 7. 安全架构

- 真理：安全 = 纵深防御：传输（HTTPS）→ 入口（CORS/限流/认证）→ 数据（隔离/脱敏）→ 审计。
- 实践：FlareError 统一错误契约（不泄露内部细节）；多租户 project_id 隔离（M5 加 tenant_id）；
  Secret 托管；日志不打印 API Key/事实全文；依赖漏洞扫描；/health 不暴露敏感信息。

## 8. 关键权衡（技术债与决策备忘）

- 开发优先 SQLite、生产上云：用协议隔离换"起步快 + 上线稳"，代价是 M5 要做迁移（有清单有纪律）；
- fail-fast 不静默降级：生产存储/模型未配置就报错，拒绝"假能跑"（F4 哲学）；
- 确定性开发嵌入（HashEmbedder 字面 n-gram）换真实嵌入（语义）：评测（M3c）会量化这个差距；
- "假抽象"警示：接口必须接线（M1 教训——recent 曾是无调用方的死参数）。

## 9. 一条需求的技术实现示例（对到三层）

- 业务：销售团队按产品文档答题；功能：知识库域检索；技术：
  文档 POST /v1/kb/documents → pipeline 切块/嵌入/入库 → kb_search 工具 → 图首轮 system 注入
  → 模型自主调用 → 观察带回引用 → 最终答案带溯源。全链路有 trace 可查（M5 起）。

## 10. 练习

1. 画出"一次带知识库检索的任务"的时序图（客户端/任务层/图/工具/存储/模型）。
2. 技术评审：如果要把 Agent 执行拆成独立微服务，哪些依赖要改成网络调用？（提示：registry、memory、checkpoint）
3. 容量题：目标 100 QPS 任务、每任务平均 3 轮模型调用，估算每分钟 LLM 调用数与所需 PG 连接数。
