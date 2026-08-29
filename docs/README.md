# 📚 Flare Agent · 文档中心（总索引 + 管理规范）

> 版本：v1.0 ｜ 日期：2026-08-27 ｜ 状态：approved
> 职责：本文档是**唯一文档入口**。先看这里，再进具体分类。
> 维护：任何文档增删改都要同步更新本文档的索引表。

---

## 一、文档分类体系（开发文档与产品文档分离）

| 目录 | 定位 | 放什么 | 面向谁 |
| --- | --- | --- | --- |
| **[product/](./product/)** | **产品与技术参考** | 需求（做什么）、调研（为什么）、架构（怎么设计） | 产品/技术所有人 |
| **[engineering/](./engineering/)** | **开发与工程规范** ⭐开发文档 | 开发流程、分支/提交/评审、测试、CI/CD、发布、SRE、安全 | 研发团队 |
| **[learning/](./learning/)** | 学习与面试 | 进阶教学、面试题库（实践+真理） | 团队学习 |
| **[adr/](./adr/)** | 架构决策记录 | 关键决策：背景→选项→决策→后果 | 研发团队 |
| **[guides/](./guides/)** | 操作指南 | 本地开发、部署、运维操作手册 | 使用者/运维 |
| **[templates/](./templates/)** | 文档模板 | ADR、需求、PR 等模板 | 写文档的人 |

> 一句话区分：**product = 这个产品是什么/为什么/怎么设计**；**engineering = 团队怎么开发与上线**。
> 两者必须分开——改需求时不看开发流程，改流程时不看需求。

## 二、文档索引（当前有效文档）

### product/ 产品与技术参考
| 文档 | 状态 | 说明 |
| --- | --- | --- |
| [research/01-market-and-tech-research.md](./product/research/01-market-and-tech-research.md) | approved | 市场与技术调研报告（竞品/选型/架构范式/阿里云） |
| [requirements/01-development-requirements.md](./product/requirements/01-development-requirements.md) | approved | 开发需求说明书 v1.0（FR/NFR/里程碑/FR-10） |
| [architecture/01-architecture-overview.md](./product/architecture/01-architecture-overview.md) | draft | 架构总览（组件/数据流/扩展/高可用/部署） |
| [architecture/02-module-design.md](./product/architecture/02-module-design.md) | draft | 模块级技术设计（目录/服务/API/数据模型/LangGraph 图/本地环境） |
| [architecture/03-design-review-m1.md](./product/architecture/03-design-review-m1.md) | review | M1 设计评审记录（结论/决策/风险/M2 范围） |
| [features/01-web-console-features.md](./product/features/01-web-console-features.md) | draft | Web Console 用户功能清单（面向最终用户，随功能迭代） |
| [analysis/01-competitive-comparison.md](./product/analysis/01-competitive-comparison.md) | approved | 功能盘点与竞品对比（Grok/Codex/DSH，差距分析与下一步优先级） |

### engineering/ 开发与工程规范（开发文档）
| 文档 | 状态 | 说明 |
| --- | --- | --- |
| [01-development-standards.md](./engineering/01-development-standards.md) | approved | 开发流程与工程规范（分支/提交/评审/测试/CI-CD/发布/SRE/安全） |
| [02-load-testing-plan.md](./engineering/02-load-testing-plan.md) | draft | 压测方案（指标/工具/场景/容量模型/验收） |
| [03-code-review-r1.md](./engineering/03-code-review-r1.md) | approved | 首轮代码审查记录（18 项处置 + 复查清单） |
| [04-code-review-r2.md](./engineering/04-code-review-r2.md) | approved | Round 2 审查记录（ReAct 交付：F1-F4 处置 + 复查清单） |
| [05-code-review-r3.md](./engineering/05-code-review-r3.md) | approved | Round 3 审查记录（Web 前端：L1-L4 + 问题2/3 处置 + 复查清单） |
| [07-code-review-r6.md](./engineering/07-code-review-r6.md) | approved | Round 6 审查记录（MCP 客户端：M1-M8 集成断点修复 + flaky 修复 + 文档 v1.1） |

### learning/ 学习与面试
| 文档 | 状态 | 说明 |
| --- | --- | --- |
| [01-agent-interview-questions.md](./learning/01-agent-interview-questions.md) | draft | 高级 Agent 工程师面试题库（实践 + 真理），FR-10 验收清单 |
| [02-rag-ingestion-pipeline.md](./learning/02-rag-ingestion-pipeline.md) | draft | RAG 入库管线与向量检索（实践 + 真理），FR-5 配套 |
| [03-memory-and-context-engineering.md](./learning/03-memory-and-context-engineering.md) | draft | 分层记忆与上下文工程（实践 + 真理），FR-4 配套 |
| [04-advanced-development-guide.md](./learning/04-advanced-development-guide.md) | draft | 进阶开发指南（分层/加工具/加 API/接模型/换存储/测试纪律），开发部分 |
| [05-production-deployment-guide.md](./learning/05-production-deployment-guide.md) | draft | 生产部署指南（阿里云 ACK/OSS/PG/Redis/OTel/多租户/容量/SLO/回滚），部署部分 |
| [06-functional-architecture.md](./learning/06-functional-architecture.md) | draft | 功能架构（功能域地图/功能清单/核心链路/依赖/NFR），实践+真理 |
| [07-business-architecture.md](./learning/07-business-architecture.md) | draft | 业务架构（价值主张/能力地图/业务流程/对象/角色/多租户/运营），实践+真理 |
| [08-technical-architecture.md](./learning/08-technical-architecture.md) | draft | 技术架构（选型/分层/运行机制/数据/集成/部署/安全/权衡），实践+真理 |
| [09-rag-evaluation-and-hybrid-retrieval.md](./learning/09-rag-evaluation-and-hybrid-retrieval.md) | draft | RAG 评测与混合检索（确定性指标/数据集/RAGAS 式判定/BM25+向量 RRF/重排），M3c 配套 |
| [10-model-gateway-and-sandbox.md](./learning/10-model-gateway-and-sandbox.md) | draft | 模型网关与沙箱（OpenAI 兼容供应商/function-calling 映射/重试/沙箱执行），M4 配套 |
| [11-web-console-and-product-ux.md](./learning/11-web-console-and-product-ux.md) | draft | Web 控制台与产品化 UX（管理页/会话切换语义/工程参数不外露/构建部署），M3a/b+Web 配套 |
| [12-production-operations-sre.md](./learning/12-production-operations-sre.md) | draft | 生产运营 SRE（SLO/错误预算/告警分级/压测/扩缩容/回滚演练），M6 配套 |
| [13-mcp-and-skills.md](./learning/13-mcp-and-skills.md) | draft | MCP 客户端与 Skills 机制（JSON-RPC/传输/工具适配/网关/技能包），FR-2/FR-3 配套 |
| [14-multi-agent.md](./learning/14-multi-agent.md) | draft | 多 Agent / Subagent 并行（任务分解/并行编排/结果聚合/预算护栏），F1.4 配套 |
| [15-openai-compat-and-cli.md](./learning/15-openai-compat-and-cli.md) | draft | OpenAI 兼容 API 与 CLI（Chat Completions 契约/SSE 流式/错误与认证/CLI 瘦客户端），F9.2/F9.3 配套 |

### adr/ 架构决策记录（14 项已记录，完整见 [adr/README.md](./adr/README.md)）
| 编号 | 标题 | 状态 |
| --- | --- | --- |
| 0001 | 数据库选型：PostgreSQL | accepted |
| 0002 | 编排引擎：LangGraph | accepted |
| 0003 | 运行时语言与 API 框架：Python + FastAPI | accepted |
| 0004 | 向量库：Milvus（主选） | accepted |
| 0005 | 会话与缓存：Redis | accepted |
| 0006 | 消息队列：RocketMQ / Kafka | accepted |
| 0007 | 对象存储：OSS / MinIO | accepted |
| 0008 | 模型网关：自研 OpenAI 兼容 | accepted |
| 0009 | 沙箱隔离：Kata/Firecracker | accepted |
| 0010 | 推理服务：vLLM / SGLang | accepted |
| 0011 | 可观测性：OpenTelemetry 栈 | accepted |
| 0012 | 前端形态：本地 Web 优先 | accepted |
| 0013 | 部署平台：阿里云 ACK（K8s） | accepted |
| 0014 | CI/CD：GitHub Actions | accepted |
| 0015 | 工程结构：Monorepo + 模块化单体优先 | accepted |

## 三、命名规范（强制）

- 每类目录内独立编号：`NNN-简短kebab-case.md`（如 `01-development-standards.md`）。
- 文件名全小写 + 连字符，**不写日期**（日期在文档头）。
- 文档标题用中文，文件名用英文（路径稳定、跨平台）。

## 四、文档头部元信息（每篇必带）

```markdown
> 版本：vX.Y  ｜ 日期：YYYY-MM-DD ｜ 状态：draft | review | approved | archived ｜ 负责人：xxx
```

- 状态定义：`draft` 草稿 / `review` 评审中 / `approved` 已批准生效 / `archived` 已归档（移入 adr 或标注弃用）。
- **approved 后才算有效文档**；draft 不得作为依据引用。

## 五、文档生命周期与变更流程

```
创建(draft) → 评审(review) → 批准(approved) → 使用中(小改则版本+0.1 / 大改则 review 重走) → 归档(archived)
```

1. 新建文档：放对分类 → 按命名规范 → 带元信息 → 在本文档索引登记（draft）。
2. 变更：走 **PR**（见 engineering 规范）；**文档变更也必须过 CI**（lint/扫描）。
3. 状态升级：draft→review→approved 要明确说明依据（评审人/决策来源）。
4. 归档：不再有效的文档标 `archived` 并注明替代文档，**不轻易删除**（保留可追溯）。
5. 大改即重评：结构/方向级改动必须走 review。

## 六、与项目记忆（CLAUDE.md / AGENTS.md）的同步规则

| 内容 | 放哪 |
| --- | --- |
| 方向、硬性约束、已决策、待决策、进度、踩坑经验 | **CLAUDE.md / AGENTS.md**（会话记忆） |
| 需求的细节、架构细节、流程细节、调研细节 | **docs/** 正文文档 |
| 影响方向的决策 | 必须**同时**写进 ADR + CLAUDE.md |

> 铁律：**改 docs 里任何影响方向的内容，必须同步 CLAUDE.md；反之亦然。**

## 七、ADR 规则（关键决策必须记录）

- 触发：技术选型、架构变更、接口/协议变更、破坏性变更。
- 模板：[templates/adr-template.md](./templates/adr-template.md)。
- 编号从 `0001` 起，永久递增不重用；见 [adr/README.md](./adr/README.md)。

## 八、模板与工具

- [ADR 模板](./templates/adr-template.md)
- （预留）需求模板、PR 模板（现用 .github/pull_request_template.md）

## 九、文档健康度检查（每月/每里程碑）

- [ ] 索引表与真实文件一致
- [ ] 无 draft 状态但被引用的文档
- [ ] 交叉引用无 404（仓库内链接）
- [ ] CLAUDE.md / AGENTS.md 与 docs 无矛盾
