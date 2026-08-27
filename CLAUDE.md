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

- ⚠️ **推送策略（2026-08-27 用户明确要求）**：默认**只在本地提交（git commit）**，**不主动推送远程仓库（不 push）**；只有用户明确要求时才 push。除非用户说"推送/提交到远程/发 PR"，一律只做本地提交。
- 生产级：可部署到真实服务，可监控、可运维、可回滚、可审计
- 高可用：多可用区、无单点、自动故障恢复
- 高并发：设计目标百万级并发（弹性的、按指标扩容；不追求"永远同时百万活跃"的虚数字）
- 可拓展：组件化、插件化（Tools / MCP / Skills / RAG 均可插拔），多模型可路由
- 技术栈：用**最强企业级技术**，接受云原生全家桶（K8s、消息队列、向量库、观测体系）
- 存储：**阿里云 OSS** 作为对象存储（代码快照、技能包、RAG 文档源、日志归档等）
- 必备 AI 能力：RAG（向量检索 + 混合检索 + 重排）、MCP 工具协议、Skills、工具系统、沙箱执行、记忆体系
- 面向人群：已掌握 demo 级 AI 开发（模型/上下文/记忆/工具/MCP/Skills 已入门），需要的是**进阶+上线**

## 3. 项目信息

- 工作区：`/d/Data/deepseekharness_project/flare-agent`（文件工具用 `D:\Data\...`，bash 用 `/d/Data/...`，两套路径格式不同！）
- **Python 环境（2026-08-27 用户明确）**：用 **conda 环境 `flare-agent`**（Python 3.12，与 CI 一致），**不用 .venv**；命令统一 `conda run -n flare-agent python ...`（等价 Makefile 的 `make test/lint/dev`）。conda 根：D:\software\conda，环境目录 D:\software\conda-envs\envs
- GitHub：仓库 `Syotick/flare-agent`（gh 已认证，账号 Syotick；**2026-08-27 由用户要求转为公开**，公开前已做敏感信息扫描）
- 版本控制：git，主分支 `main`，中文 commit message 允许（团队用中文）；PR 分支规范见 docs/engineering
- ⚠️ **GitHub 流程已启用（2026-08-27）**：main 已开**分支保护**——直推 main 会被拒绝（admin 可绕过），必须走 `feat/*` 分支 + PR；PR 需通过 CI 门禁（status check: `Required Status Gate`）。合并方式：squash/rebase（已禁 merge commit）。仓库已配：LICENSE(MIT)/CONTRIBUTING/CODE_OF_CONDUCT/SECURITY/Issue&PR 模板/ci/release/stale/dependabot/pre-commit/labels/milestones(M1-M6)
- 📚 **文档体系（2026-08-27 重构）**：docs/README.md 是**唯一入口**；product(调研/需求/架构) / engineering(开发规范) / learning(面试) / adr / templates / guides 分类；开发文档与产品文档分离；**改 docs 影响方向时必须同步 CLAUDE.md**（规则见 docs/README §6）。
- ✅ **CI 现状（2026-08-27）**：main 上 CI 全绿（lint/test/scan/gate），PR #1 已走通全流程。已移除 CodeQL（私有仓库未启用 code scanning 且暂无代码）——待有代码且开启 code scanning 再补回。Dependabot 在无 manifest 时会产生 benign 失败 run，属正常。
- 🌐 **网络**：git 直连 github.com 会失败，需走代理（已配 `git config --global http.proxy http://127.0.0.1:7890`，Clash 端口）；gh 走 api.github.com 无需代理。
- 💡 **踩坑经验**：① GitHub Actions 的 YAML 里内联 `run: echo "TODO: xxx: yyy"` 这种「值含冒号+空格」必须用 block scalar（`run: |`），否则 workflow 解析失败（run 0 秒失败、workflow 名变文件路径）。② 分支保护的 required status check context 必须与 GitHub 实际生成的 check-run 名称一致——本项目是 `Required Status Gate`（不是 `CI / Required Status Gate`），名称不匹配会导致 PR mergeStateStatus=BLOCKED。③ gitleaks-action@v2 在 PR 模式需要 workflow `permissions: pull-requests: read`，否则 403。
- **开发规范（强制）**：docs/engineering/01-development-standards.md（分支/提交/评审/测试/CI-CD/发布/SRE/安全）
- **代码审查（2026-08-27 起）**：首轮审查记录 docs/engineering/03-code-review-r1.md（18 项意见已处置，8 项复查清单待下轮核对）；后续每轮审查结果都归档到 engineering/
- 当前阶段：M0 完成 + 需求已确认（技术栈/形态/沙箱），进入 M1 设计评审 / M2 开发准备

## 4. 已做决策（按时间倒序，最新在上）

| 时间 | 决策 |
| --- | --- |
| 2026-08-27 | 仓库名 `flare-agent`（私有）；采用 monorepo 风格目录：docs + 未来 services/ 模块 |
| 2026-08-27 | 记忆体系：CLAUDE.md + AGENTS.md 双写；docs/ 已按分类重构：product(调研/需求/架构)/engineering(开发规范)/learning(面试)/adr/templates，入口 docs/README.md |
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

## 6. 里程碑（详细版见 docs/product/requirements/01-development-requirements.md §6）

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
