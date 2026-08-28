# Flare Agent · 功能盘点与竞品对比（Grok / Codex / DSH）

> 版本：v1.0 ｜ 日期：2026-08-28 ｜ 状态：approved ｜ 负责人：Flare 团队
> 目的：对当前 8 大功能域做一次对照 FR 的能力盘点，并与 Grok / Codex / DeepSeek Harness（DSH）
> 做横向对比，据此确定下一步开发优先级。
> 方法：对比基于公开信息 + 对 DSH 的一手使用经验；细节随各产品版本演进会变。

---

## 1. 当前功能盘点（按 8 功能域，对照 FR）

| 功能域 | 已交付 | 状态 |
| --- | --- | --- |
| 用户/组织 | 多租户 X-Tenant-Id→contextvar 隔离（M5） | ✅；用户体系/SSO/RBAC/配额 ⏳ |
| 会话任务 | POST 202 + SSE 真流式 + 详情/列表/删除 + 同线程续聊 + hash 恢复（M2/M3b） | ✅；interrupt 审批 ⏳ |
| Agent 执行 | LangGraph ReAct 循环、工具调用、max_steps 预算熔断、checkpoint 可恢复（M2/M5 PG） | ✅；多 Agent 并行 ⏳ |
| 知识库 RAG | 入库管线、hybrid（BM25+向量 RRF）+ rerank、溯源、RAG 评测（M3a/c） | ✅；多格式解析/版本化/权限 ⏳ |
| 记忆 | 三层记忆（短期对话/长期事实/向量）+ 上下文工程预算（M3b） | ✅ |
| 工具 | 注册表 + JSON Schema 校验 + 失败观察 + schema 注入 system（M2） | ✅；MCP ⏳ / Skills ⏳ |
| 模型网关 | mock + OpenAI 兼容 + function-calling 映射 + 指数重试（M4） | ✅；多模型路由/配额/缓存 ⏳ |
| 沙箱 | LocalProcessSandbox（超时/输出/内存上限）+ Docker 占位 fail-fast（M4） | ✅；容器强隔离 ⏳ |
| 管理运维 | /health、错误契约、SLO/错误预算/告警分级/压测/发布门禁/指标（M6） | ✅ 领先 |
| Web 控制台 | 对话 / 知识库 / 记忆 / 运维中心 四工作区 | ✅ |
| 工程化 | 121 单测、ruff/black、CI、Dockerfile + K8s 7 清单、reconcile 双写对账（M5） | ✅ |

**能力全景一句话**：一个"模块化单体 + 零依赖本地可跑"的企业级 Agent 平台——编排/工具/记忆/RAG/网关/沙箱/运维/多租户八件套齐了，
前端控制台四区齐全，运维可观测性反而比多数成熟产品还全。

## 2. 与 Grok / Codex / DSH 的对比

### 2.1 各自定位

- **Grok（xAI）**：通用 + 实时信息 Agent（消费级）+ Agent Tools API（开发级）。背靠 X 生态，search（实时网页+X）、
  memory（短/长期/自记忆）、computer-use（浏览器）、图片理解/生成，2025 推出 Grok 4.1 Fast + Agent Tools API 面向真实业务。
- **Codex（OpenAI）**：开发者编码 Agent——CLI/IDE/手机 App（watch mode）+ 云并行任务（隔离 VM 沙箱跑 ~30min 任务）+
  review 模式 + skills（SKILL.md）+ AGENTS.md 项目记忆 + MCP 客户端，付费订阅制（约 $200/月档起）。
- **DSH（DeepSeek Harness）**：本地优先的 Agent 工程 harness——profile+插件 patch 分层组合；多 Agent 编排是主打
  （subagent/workflow/goal/Ralph，36kr 原文："把 spawn 子 Agent 做成了协议"）；全栈工具（bash/文件/ssh/web/grep/vision）；
  PTC 模式 + 文件策略沙箱；skills；150k+ star。

### 2.2 关键维度对比

| 维度 | Flare Agent（我们） | Grok | Codex | DSH |
| --- | --- | --- | --- | --- |
| 定位 | 企业级可上线平台 | 实时通用 Agent | 编码 Agent（云并行） | 本地 harness/协议 |
| 核心循环 | LangGraph ReAct+SSE | 推理+DeepSearch+工具 API | agentic coding+云沙箱 | 会话+多 Agent 编排 |
| 工具系统 | 注册表+Schema 校验 | Agent Tools API | 文件/bash/Git/MCP/技能 | bash/文件/ssh/web 全栈 |
| MCP/Skills | ⏳ FR-2/FR-3 未做 | 有工具 API | 有（MCP+skills） | 有 skills |
| 多 Agent 并行 | ⏳ F1.4 未做 | 少 | 云并行任务 | 主打（子代理/工作流） |
| 记忆 | 三层+上下文工程 | 用户级记忆 | AGENTS.md 项目记忆 | 会话压缩+goal 持久化 |
| RAG/知识库 | hybrid+rerank+评测 | 实时搜索 | 语义搜索（弱） | web_search 工具 |
| 沙箱 | 本地进程+Docker 占位 | computer-use（浏览器） | 云隔离 VM | 文件策略沙箱+PTC |
| 运维/治理 | SLO/告警/压测/门禁/多租户/OTel | 企业版 DeployGrok | 权限分级+审计+计费 | 本地 job/会话管理 |
| 部署形态 | 本地 / 待云（ACK） | 云 API | 云 | 本地/自托管 |

## 3. 差距与启示（下一步往哪走）

### 3.1 我们明显领先的

- **运维治理**：SLO/错误预算/告警/压测/门禁——成熟产品大多没有这么完整的工程闭环
- **三层记忆 + 上下文工程**（短期对话/长期事实/向量 + 预算）
- **RAG 评测体系**（确定性指标 + RAGAS 式判定 + 混合检索）
- **多租户 + 可插拔存储**（M5）

### 3.2 与成熟产品最大的三个差距（恰好全是本地可做的）

1. **MCP 客户端 + Skills（FR-2/FR-3）**——Codex/DSH/Grok 全都有，是"生态接入"的标配，也是面试高频考点；
2. **多 Agent / Subagent 并行（F1.4）**——DSH 的招牌、Codex 的云并行核心，我们目前是单线程任务；
3. **接入形态：CLI（F9.2）与 OpenAI 兼容 REST API（F9.3）** 预留未落地——Codex 靠 CLI 立身。

### 3.3 排序建议

按"差距大 + 本地可做 + 面试价值"排序：**MCP/Skills → 多 Agent 并行 → CLI**。

其中 **MCP 客户端对"对标成熟产品"的补课价值最高**——既能接外部工具生态，又天然串起 FR-2 的网关/认证/审计设计。

### 3.4 决策（2026-08-28）

- ✅ 下一步开发点：**MCP 客户端 + Skills（FR-2 / FR-3）**
- MCP 范围：客户端连接（SSE / Streamable HTTP）+ 工具适配进现有 Registry + 统一 MCP 网关（认证/白名单/限流/审计）
- Skills 范围：声明式技能包（SKILL.md 风格：清单 + 提示词 + 资源 + 工具依赖），可安装/卸载/列表
