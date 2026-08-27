# CLAUDE.md — Flare Agent 项目记忆

> 本文件是**项目持久记忆**。新会话 / 切换模型 / 换工具时，第一件事是读取本文件，
> 以恢复项目上下文，避免遗忘目标、约束、进度和已做决策。
> 维护规则：任何影响方向/架构/决策的变更，必须同步更新本文件（和 AGENTS.md）。

---

## 1. 项目一句话目标

构建一个**企业级、可上线、高可用、可拓展**的 AI Agent 平台，对标
OpenAI Codex / Claude Code / DeepSeek Harness，估算并发 **百万级**，部署在 **阿里云**，
对象存储用 **阿里云 OSS**，并集成 **RAG** 等最新 AI 能力。
**不是 demo，是要上生产、可运维、可管理的东西。**

## 2. 硬性要求（不可违背）

- 生产级：可部署到真实服务，可监控、可运维、可回滚、可审计
- 高可用：多可用区、无单点、自动故障恢复
- 高并发：设计目标百万级并发（弹性的、按指标扩容；不追求"永远同时百万活跃"的虚数字）
- 可拓展：组件化、插件化（Tools / MCP / Skills / RAG 均可插拔），多模型可路由
- 技术栈：用**最强企业级技术**，接受云原生全家桶（K8s、消息队列、向量库、观测体系）
- 存储：**阿里云 OSS** 作为对象存储（代码快照、技能包、RAG 文档源、日志归档等）
- 必备 AI 能力：RAG（向量检索 + 混合检索 + 重排）、MCP 工具协议、Skills、工具系统、沙箱执行、记忆体系
- 面向人群：已掌握 demo 级 AI 开发（模型/上下文/记忆/工具/MCP/Skills 已入门），需要的是**进阶+上线**

## 3. 项目信息

- 工作区：`/d/Data/deepseekharness_project/flare-agent`
- GitHub：私有仓库 `Syotick/flare-agent`（gh 已认证，账号 Syotick）
- 版本控制：git，主分支 `main`，中文 commit message 允许（团队用中文）
- 当前阶段：阶段 0 完成（Git + 文档 + 记忆），等待用户确认需求后进入阶段 1 设计评审

## 4. 已做决策（按时间倒序，最新在上）

| 时间 | 决策 |
| --- | --- |
| 2026-08-27 | 仓库名 `flare-agent`（私有）；采用 monorepo 风格目录：docs + 未来 services/ 模块 |
| 2026-08-27 | 记忆体系：CLAUDE.md + AGENTS.md 双写，docs/ 放调研/需求/架构 |
| 2026-08-27 | 技术方向初选（待评审）：Agent 运行时主语言 **Python**（生态最强，LangGraph/CoAgents 等）；控制面可 TS |
| 2026-08-27 | 对象存储定为**阿里云 OSS**；向量库候选 Milvus/Qdrant/pgvector（需求评审时定夺） |
| 2026-08-27 | 并发目标表述统一为：**可弹性扩展到百万级并发接入**，不承诺恒定百万在线 |
| 2026-08-27 | ✅ 技术栈**定稿**：Python + LangGraph + FastAPI + Milvus（主选）；模型网关自研(OpenAI 兼容)；推理可自托管 vLLM/SGLang |
| 2026-08-27 | ✅ 产品形态：**本地 Web 优先**（Web 控制台 + 预留 CLI/API） |
| 2026-08-27 | ✅ 沙箱路线：**"最能秀肌肉"的强隔离**——微虚拟化级（Kata Containers / Firecracker microVM），本地开发用 Docker 降级模式，架构上沙箱可插拔 |
| 2026-08-27 | ✅ 阿里云凭证**后续提供**：开发阶段用本地模拟（MinIO 模拟 OSS、本地 Redis/PG/向量库），存储层做成可切换 Provider |
| 2026-08-27 | ✅ 新增需求：**面试题驱动开发**——全面覆盖高级 Agent 工程师考点（多路召回/GraphRAG/记忆/安全/高并发等），实践(落地代码)+真理(理论)并重 |

## 5. 待决策 / 待用户确认（剩余阻塞点）

1. ~~技术栈~~ ✅ 已定（Python+LangGraph+Milvus）
2. 阿里云账号/凭证：**后续提供**，先用本地模拟开发，不阻塞
3. ~~产品形态~~ ✅ 本地 Web 优先
4. ~~沙箱~~ ✅ Kata/Firecracker 强隔离（开发期 Docker 降级）
5. 预算与模型供应商（阿里云百炼？OpenAI/Claude/DeepSeek 自接？）——开发先默认 DeepSeek/通义兼容接口 + 可配置多供应商
6. ~~沙箱合规~~ ✅ 按企业级微虚拟化做
7. 团队规模与运维人力（决定自动化程度）——暂按单人全栈推进

## 6. 里程碑（详细版见 docs/requirements/01-development-requirements.md §6）

- M0 项目准备（Git/仓库/文档/记忆）✅
- M1 需求评审与架构评审（等用户）
- M2 核心 Agent 引擎（agent loop + 工具系统 + 会话）
- M3 RAG 知识库 + 记忆体系
- M4 多模型路由 + 推理服务 + 成本控制
- M5 云原生部署（阿里云 ACK + OSS + 可观测）+ 压测
- M6 上线、灰度、SLO 运营

## 7. 常用命令备忘

```bash
# 推送
git add -A && git commit -m "msg" && git push origin main
# 创建私有仓库（如已删）
gh repo create flare-agent --private --source . --remote origin --push
# 当前分支
git branch --show-current
```

## 8. 铁律（编码约束）

- 任何密钥/凭证**绝不入库**（见 .gitignore），一律走环境变量 / K8s Secret / Vault
- 用户数据（代码快照、RAG 文档、会话）先落 OSS/持久化，内存只做缓存
- 所有外部依赖评估生产化程度（维护活跃度、许可证、云上托管能力）后再引入
- 面向百万并发：有状态东西尽量外置（Redis/DB/消息队列），应用层无状态、水平扩展
