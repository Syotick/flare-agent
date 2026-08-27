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
- **代码审查（2026-08-27 起）**：R1=engineering/03（18项）；R2=engineering/04（F1-F4）；R3=engineering/05（Web前端 L1-L4+问题2/3，真流式/SSE生命周期/折叠滚动/刷新恢复）；后续每轮审查结果都归档到 engineering/
- **M2 代码结构（2026-08-27）**：services/ 已开工——共享库 flare_common + agent_runtime(LangGraph ReAct 图 + 任务API **POST 立即返回202 + SSE 真流式 + GET 详情/列表/DELETE 删除**) + tools_gateway + model_gateway + **web Console(Vite+React+TS)** + rag/sandbox 占位；pip install -e . 可安装；pytest 32 全绿，ruff/black 干净；make web-dev/web-build 管前端
- **Web 前端栈（2026-08-27 定，参考 nova-agent D:/Data/.../nova-agent/src）**：Vite5 + React18 + **Tailwind v4(@tailwindcss/vite) + shadcn 风格(Radix: alert-dialog/dropdown-menu) + lucide-react 图标** + cva/clsx/tailwind-merge；**flare 耀斑主题**（styles.css @theme 琥珀金令牌 + 太阳日冕径向渐变背景 + 灰烬粒子 + corona-drift/辉光动画）；组件：FlareLogo(SVG太阳+日珥轨道)/ThinkingOrb/FlareLogo 思考光球/Sidebar(品牌+会话搜索分组+删除确认AlertDialog+导航+状态)/Composer(工具栏+autosize textarea+渐变发送/停止)/ChatView(用户/助手气泡+StreamText打字机+ToolCallCard药丸折叠)/WelcomePanel(示例卡)/ui 组件(button/input/card/alert-dialog/dropdown-menu)；后端 API：GET /v1/tasks、DELETE /v1/tasks/{id}、POST/SSE；包体：CSS gzip 7KB(仅用到的类)+JS 分包(vendor-react/radix/lucide/ui)
- **learning 教学文档扩展（开发+生产）**：新增 04-进阶开发指南（分层/加工具/加API/接真实模型/换存储底座/测试纪律踩坑合集/开发→生产切换矩阵）+ 05-生产部署指南（阿里云 ACK/OSS/PG/Redis/OTel/多租户/容量/SLO/回滚/上线清单，已实现✅与M5/M6⏳标注）；顺带修复 pyproject packages.find 缺 memory* 的部署阻断（wheel 不含 memory 包），pip install -e . 验证通过。
- **Round5 审查修复（M3b 交付）**：M1 三层记忆真正接线——TaskManager 从 checkpointer 取该线程近期对话传 build_context(recent=)，graph actor 支持同 thread 续聊追加新输入；M2 mem_recall 按相关度排序+封顶 k+2 条不再全量倾倒；M3 向量记忆溯源可读（文本前缀+短id）；M4 事实进上下文按最新 15 条封顶；M5 pgvector 迁移决策（同 PG 分表 kb_chunks/memory_chunks）；M6 thread_id 续聊语义文档化。pytest 60 全绿。
- **Round4 审查修复（M3a 交付）**：R1 工具 schema 经 system 消息注入（graph._build_tool_schema），真实模型才能自主调 kb_search（新增 test_agent_autonomously_calls_kb_via_system_schema）；R2 重复入库先删旧 chunk 再插；R3 content 上限 100k；R4 k 限 1..20 + 维度校验 VECTOR_DIM_MISMATCH；R6 暴露 HashEmbedder 字面非语义边界；R7 观察截断 200→300。pytest 56 全绿。
- 当前阶段：**M2 完成核心闭环**；**M3a RAG 知识库 ✅ + M3b 分层记忆 ✅**（services/memory：短期=checkpoint 会话 + 长期=事实库 facts(key->value,project_id 隔离) + 向量=复用 rag 协议 + F4.3 上下文工程 context.py + mem_set/mem_recall 工具 + /v1/memory API(facts CRUD/notes/search/context) + 任务开始自动注入记忆上下文(graph memory_context) + test_memory 10 例 + scripts/demo_memory.py + learning/03；pytest 52 全绿，ruff/black 干净）。下一步：M3c RAG 评测（RAGAS/混合检索/重排）或把知识库/记忆管理页接进 Web 控制台

## 4. 已做决策（按时间倒序，最新在上）

| 时间 | 决策 |
| --- | --- |
| 2026-08-27 | 仓库 flare-agent 已公开；monorepo：services/(flare_common 共享库 + agent_runtime/model_gateway/tools_gateway/rag/sandbox) + infra + eval + tests；模块化单体优先(ADR-0015)，可 pip install -e . |
| 2026-08-27 | 共享库命名 flare_common（带命名空间、可独立安装），对齐按服务拆分演进（审查 D1） |
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
- M1 需求与架构评审 ✅（ADR ×15、模块设计、压测方案、评审记录）
- M2 核心 Agent 引擎（agent loop + 工具系统 + 会话）🔨 核心闭环 ✅（工具/ReAct/任务API/SSE/Web Console）
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
