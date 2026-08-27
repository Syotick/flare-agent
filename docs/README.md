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

### engineering/ 开发与工程规范（开发文档）
| 文档 | 状态 | 说明 |
| --- | --- | --- |
| [01-development-standards.md](./engineering/01-development-standards.md) | approved | 开发流程与工程规范（分支/提交/评审/测试/CI-CD/发布/SRE/安全） |
| [02-load-testing-plan.md](./engineering/02-load-testing-plan.md) | draft | 压测方案（指标/工具/场景/容量模型/验收） |
| [03-code-review-r1.md](./engineering/03-code-review-r1.md) | approved | 首轮代码审查记录（18 项处置 + 复查清单） |

### learning/ 学习与面试
| 文档 | 状态 | 说明 |
| --- | --- | --- |
| [01-agent-interview-questions.md](./learning/01-agent-interview-questions.md) | draft | 高级 Agent 工程师面试题库（实践 + 真理），FR-10 验收清单 |

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
