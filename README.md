# Flare Agent · 企业级 AI Agent 平台

> 对标 **OpenAI Codex / Anthropic Claude Code / DeepSeek Harness** 的企业级、可上线、高可用、可拓展的 AI Agent 平台。
> 面向已掌握 demo 级 AI 开发（模型、上下文、记忆、工具、MCP、Skills）的进阶开发者。

## 核心定位

- **产品形态**：云端 AI Coding / 通用 Agent 平台，Web + CLI + API 三端接入
- **并发目标**：百万级并发接入（设计目标），弹性伸缩
- **运行环境**：阿里云（OSS 对象存储 + K8s/ACK + 云原生全家桶）
- **必备能力**：RAG、MCP、Skills、工具系统、沙箱执行、多模型路由、可观测、可审计

## 文档导航

| 文档 | 说明 |
| --- | --- |
| [CLAUDE.md](./CLAUDE.md) | **项目记忆**（会话恢复时优先读取） |
| [docs/research/01-market-and-tech-research.md](./docs/research/01-market-and-tech-research.md) | 市场与技术调研报告 |
| [docs/research/02-agent-interview-questions.md](./docs/research/02-agent-interview-questions.md) | 高级 Agent 工程师面试题库（实践 + 真理） |
| [docs/requirements/01-development-requirements.md](./docs/requirements/01-development-requirements.md) | 开发需求说明书 |
| [docs/architecture/01-architecture-overview.md](./docs/architecture/01-architecture-overview.md) | 架构总览 |
| [docs/engineering/01-development-standards.md](./docs/engineering/01-development-standards.md) | 开发流程与工程规范（CI/CD/测试/评审/发布/SRE） |

## 状态

- [x] 阶段 0：项目准备（Git + GitHub 私有仓库 + 文档骨架）
- [ ] 阶段 1：需求评审（等待确认后开工）
- [ ] 阶段 2：核心 Agent 引擎
- [ ] 阶段 3：RAG / 知识库
- [ ] 阶段 4：多模型路由与推理服务
- [ ] 阶段 5：云原生部署（阿里云）+ 可观测
- [ ] 阶段 6：压测与上线

> 详细里程碑见开发需求说明书 §6。
