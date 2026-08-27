# Flare Agent · 开发流程与工程规范（Development Standards）

> 版本：v1.0 ｜ 日期：2026-08-27 ｜ 状态：**项目级强制规范（独立于业务代码）**
> 定位：沉淀成熟互联网公司的研发流程与规范（版本控制、提交、评审、测试、CI/CD、发布、SRE、安全），
> 作为 Flare Agent 日常开发/协作/上线的执行标准。团队/协作者/后续会话一律遵守。

---

## 0. 目的与适用范围

- 保证：**可评审、可测试、可回滚、可审计、可复盘**——这是"企业级"区别于 demo 的根本。
- 适用范围：本项目所有代码、配置、文档、流程（单人开发也照此执行，为多人协作做准备）。

## 1. 版本控制与分支策略

### 1.1 三种主流策略对比（选型依据）

| 策略 | 特点 | 适合 | 风险 |
| --- | --- | --- | --- |
| **Git Flow** | main/release/develop + feature/hotfix 多分支 | 发版节奏固定的传统项目 | 分支多、合并且复杂度高 |
| **GitHub Flow** | 只有 main + feature/PR；小步快跑，随时可发 | 持续交付、CI 强、小团队 | 需要纪律与强 CI |
| **Trunk-Based** | 全部直接/短期分支合入 main，主干即生产 | 大厂（Google 等）、追求极致部署速度 | 对 CI 与测试要求最高 |

> 参考：[Trunk-Based vs GitFlow（Stxnext）](https://www.stxnext.com/blog/escape-merge-hell-why-i-prefer-trunk-based-development-over-feature-branching-and-gitflow)、[Git 工作流选型对比](https://m.zpedu.com/it/rjyf/38685.html)。

### 1.2 本项目策略（落地）

- **采用 GitHub Flow 起步**：`main` 始终可部署 + 功能分支 `feat/xxx` + PR 合入。
- 演进路径：团队扩到多人、部署频率上来后，迁移到 **Trunk-Based**（PR 变小、合入即上）。
- 规则：
  - 禁止直接向 `main` 提交（除 hotfix 紧急且经审批）。
  - PR 必须过 CI（lint/测试/构建/扫描）才能合入；`main` 保持绿色。
  - 分支命名：`feat/<模块>-<简述>`、`fix/<简述>`、`docs/<简述>`、`chore/<简述>`。
  - 环境与发布走标签/Release（`vX.Y.Z`），不用长命分支模拟环境。

## 2. 提交与 PR 规范

### 2.1 Conventional Commits（提交信息规范）

```
<type>(<scope>): <subject>   # 如 feat(rag): 多路召回 + RRF 融合
```
- type：`feat` / `fix` / `docs` / `chore` / `refactor` / `perf` / `test` / `build` / `ci` / `security`。
- scope：模块名（agent-runtime / rag / gateway / web / infra…）。
- 一条提交只做一件事；主题 <= 50 字符，正文说明"为什么"。
- 意义：自动生成 changelog、CI 可据此决定跳过构建、回溯定位方便。
> 参考：[社区 Commit 与 PR 规范](https://gitcode.com/jiaxuan_wong/ohos_react_native_0605/blob/main/docs/zh-cn/06-%E7%A4%BE%E5%8C%BA/%E7%A4%BE%E5%8C%BAcommit%E5%92%8Cpr%E8%A7%84%E8%8C%83.md)。

### 2.2 PR 规范
- **小 PR**：一次评审 200~400 行以内，聚焦单一变更（Google 实践：越小的 CL 越早被审、越少缺陷）。
- PR 描述用模板：**背景 / 改动 / 测试方式 / 影响面 / 是否需回滚说明**。
- 关联 Issue/需求编号；合入前必须：CI 全绿 + 有评审 + 必要测试。
> 参考：[Google Code Review Playbook（DeployHQ 翻译解读）](https://www.deployhq.com/blog/google-code-review-playbook-deployment-velocity)。

## 3. 代码评审 Code Review

### 3.1 原则（Google / 大厂共识）
- 评审重**正确性与长期可维护性**，不吹毛求疵风格；遇到分歧尊重作者判断并给依据。
- 默认"合入是常态，拦截是例外"；作者有责任把 PR 做得易审（小、有测试、有说明）。
- 评审人职责：检查正确性、可测试性、安全、性能、命名、是否引入反模式、是否缺测试。

### 3.2 Review Checklist（本项目强制）
- [ ] 逻辑正确、边界处理（空/超限/并发/超时）
- [ ] 有对应测试（unit / integration / eval），覆盖关键路径
- [ ] 无密钥/敏感信息入库（含日志、示例）
- [ ] 输入校验与注入防护（LLM 输入视为不可信）
- [ ] 可观测性（关键路径有 trace/指标/日志）
- [ ] 错误处理与重试/幂等
- [ ] 依赖变更是否合理（新增依赖需理由）
- [ ] 兼容性/迁移（DB 变更、配置变更文档化）
- AI 辅助：可用 AI 做初筛，但**人必须终审**（AI 也会漏安全和业务语义）。

> 参考：[Google Pigweed Code Review 文档](https://android.googleid.googlesource.com/platform/external/pigweed/+/refs/heads/sdk-release/docs/code_reviews.rst)、[大厂 Code Review 规范实例（字节飞书）](https://datasea.cn/go0218496919.html)。

## 4. 测试体系

### 4.1 测试金字塔（大厂共识）

```
      /   E2E（少量、端到端、慢）        ~5-10%
     /-- 集成/契约（服务间、DB/外部依赖） ~20-30%
    /---- 单元测试（快、多、确定性）      ~60-70%
```
> 参考：[从单测到压测：大厂测试金字塔（腾讯云）](https://cloud.tencent.com.cn/developer/article/2584819)。

- **单元**：函数/类级，无外部依赖（mock）；覆盖率目标 **>= 70%**（核心模块 >= 80%）。
- **集成**：真实 DB/Redis/向量库/对象存储（本地 Docker 起依赖）跑服务间链路。
- **契约**：API schema 契约测试（OpenAPI/OpenAI 协议兼容），防供应商漂移。
- **E2E**：核心用户旅程（发起任务→agent 执行→审批→交付）跑通，CI 每 PR 跑冒烟、夜间全量。
- **压测**：k6/Locust 做容量与稳定性（对应 M5），结果进报告。

### 4.2 AI/LLM 项目特有测试（本项目强制）
- **Eval 先行（eval-driven）**：改 prompt/模型/检索前先有基准集，改动必须跑评测对比。
- **Golden Set（黄金数据集）**：固定输入 + 期望输出/判定标准；RAGAS + 任务成功率双轨。
- **Prompt/模型版本管理**：prompt 入库（版本化），模型配置记录灰度批次。
- **回归保护**：线上 bad case 回流成回归用例；数据/行为漂移监控（embedding 分布、命中率、幻觉率）。
- **非确定性处理**：LLM 输出有随机性——测试用"断言要点/打分"而非逐字相等，必要时固定温度/seed 做快照。

## 5. CI/CD 流水线

### 5.1 流水线阶段（GitHub Actions 落地模板）

```
[PR]  lint → unit tests → build → 依赖扫描 → 密钥扫描 → 集成测试(可选) → eval(可选) → 冒烟
[push main] 上述 + 构建镜像 → 推 ACR → staging 部署 → staging 验证(eval/smoke)
[tag v*]    prod 金丝雀 → 灰度观察 → 全量 → 监控 SLO
```

- 每个阶段**失败即阻断**；流水线即"产品是否可合入/可上线"的裁判。
- 环境变量/密钥只经 GitHub Secrets 或云 Secret 注入，**绝不进仓库**。
> 参考：[CI/CD 最佳实践（skillstack）](https://github.com/viktorbezdek/skillstack/blob/main/debugging/skills/debugging/references/cicd-best_practices.md)、[AI 工程 CI/CD：从模型发版到 Skill 灰度（腾讯云）](https://cloud.tencent.com.cn/developer/article/2671652)。

### 5.2 环境管理
- 三环境：**dev（本地/Docker 全家桶）→ staging（预发，跑完整 eval）→ prod（线上）**。
- 配置 12-Factor：配置走环境变量/配置中心，代码不含环境差异。
- 数据隔离：staging 用脱敏数据，禁止真用户数据。

## 6. 发布与变更管理

### 6.1 部署策略对比（选型依据）

| 策略 | 机制 | 优点 | 风险 | 适用 |
| --- | --- | --- | --- | --- |
| 滚动更新 | 分批替换 | 简单、零停机 | 故障波及面逐步扩大 | 常规后端 |
| 蓝绿 | 两套环境切流 | 回滚极快 | 双倍资源 | 关键服务 |
| 金丝雀 | 小流量灰度新版本 | 风险最小、可观察 | 需流量控制与观测 | **本项目默认** |

> 参考：[金丝雀/滚动/蓝绿发布差别与关键点（腾讯云）](https://cloud.tencent.cn/developer/article/2003685)、[部署策略（Microsoft Learn）](https://learn.microsoft.com/zh-cn/training/modules/improve-reliability-deployment/5-strategies)。

### 6.2 本项目发布规则
- **默认金丝雀**：5%→20%→50%→100%，每档观察 SLO 与错误率，异常即自动/手动回滚。
- **特性开关（Feature Flag）**：大功能用 flag 控制曝光，代码先上、功能后放（参考：特性开关工程实践）。
- 发布窗口：重大变更避开高峰；发布必须可回滚（DB 迁移向前兼容、镜像保留、回滚预案）。
- 变更记录：CHANGELOG + Release Notes；重大变更走变更评审。

## 7. 可观测、监控与值班

### 7.1 SLO / SLI
- 定义核心 SLI：可用性、P95/P99 延迟、错误率、成功率（任务/工具/检索）、成本。
- SLO 目标（对应需求 N1）：可用性 >= 99.95%，首 token P95 < 2s 等；超阈自动告警。
- **告警规则**：只告警"需要人处理"的信号；配告警静默/聚合/分级（P0/P1/P2）。

### 7.2 值班与故障复盘（Blameless）
- 值班（on-call）：明确响应时限（P0 15min 内响应）、值班手册（runbook：先止损→定位→修复→复盘）。
- **无指责复盘（Blameless Postmortem）**：只问"流程哪里让系统失败"，不追责个人；产出行动项并跟踪闭环。
- 教训参考：**语雀 P0 事故复盘**——配置/发布缺乏防护、变更无评审、监控缺失、人工操作无兜底，是反例教科书。
> 参考：[语雀 P0 事故复盘（力扣转载）](https://leetcode.cn/discuss/post/3577963/yu-que-p0-shi-gu-fu-pan-by-liyupi-pudq/)、[腾讯 SRE 质量运营体系](https://www.itilchina.cn/achotsao/vip_doc/29189638.html)。

## 8. 配置、密钥与环境

- 12-Factor：配置外部化；同环境一致、跨环境隔离。
- **密钥管理**：一律走环境变量 / 云 Secret（K8s Secret / Vault / 云 KMS），**禁止提交、禁止硬编码、禁止打日志**。
- 本地开发：.env.example 提供模板，真实 .env 进 .gitignore。
- 依赖锁定：Python 用 `uv.lock`/pip-tools，Node 用 lockfile；CI 用锁文件安装。

## 9. 安全开发（Secure SDLC）

- **依赖扫描**：CI 中 `pip-audit` / `osv-scanner` / Dependabot 持续拉取漏洞告警。
- **密钥/泄露扫描**：gitleaks / trufflehog 进 CI，阻止密钥入库（本项目已有 .gitignore 双保险）。
- **安全评审**：涉及认证、权限、支付、数据导出、沙箱的功能必须过安全评审。
- **供应链**：锁依赖 + 校验镜像签名 + 最小权限的 CI token。
- **LLM 特有**：输入不可信（防 Prompt 注入）、输出过滤（PII/敏感）、工具最小权限、沙箱隔离执行。
> 参考：[Secure SDLC Best Practices（TigerGate）](https://www.tigergate.dev/resources/security/secure-sdlc/)、[Dev Practices（Sensei Docs）](https://docs.senseiiq.cloud/docs/security/development-practices)。

## 10. 文档与知识管理

- **ADR（架构决策记录）**：每个关键决策（选型、架构变更）写 `docs/adr/NNN-xxx.md`：背景→选项→决策→后果。
- 每个服务/模块 README：职责、本地启动、测试、配置项。
- **项目记忆**（本仓库 CLAUDE.md / AGENTS.md）：方向/约束/决策/进度，任何影响方向的变更必须同步更新。
- 规范类文档（本文档）作为强制约定，随实践迭代更新版本号。

## 11. AI/LLM 工程特有规范（汇总）

1. **Eval Gate**：prompt/模型/检索变更，未过评测不允许上线（对应 CI 阶段 eval）。
2. **模型与 Prompt 版本化**：版本号随部署记录，可回滚（模型回退=配置回退）。
3. **成本治理**：token/费用按租户计量、配额、告警；缓存与模型分级降本。
4. **数据合规**：训练/评测数据脱敏；用户数据删除权；数据驻留（OSS 地域）。
5. **可观测性**：模型/工具/检索全部按 OpenTelemetry GenAI 语义埋点，一次任务一条 trace。

## 12. 在 Flare Agent 的落地清单（待 M2 起执行）

- [ ] `.github/workflows/ci.yml`：PR 流水线（lint + unit + build + scan + smoke）
- [ ] `.github/workflows/release.yml`：tag 触发 → 镜像 → staging → 金丝雀
- [ ] 目录约定 `tests/`（unit/integration/e2e）+ `eval/`（golden set + RAGAS）
- [ ] Conventional Commits + PR 模板（`.github/pull_request_template.md`）
- [ ] gitleaks + pip-audit + Dependabot 进 CI
- [ ] `docs/adr/` 目录与 ADR 模板
- [ ] 三环境配置模板（.env.example / staging / prod）
- [ ] SLO 指标定义文档 + 告警规则（对接 M5 观测体系）

## 13. 参考来源

- [Trunk-Based Development vs GitFlow（Stxnext）](https://www.stxnext.com/blog/escape-merge-hell-why-i-prefer-trunk-based-development-over-feature-branching-and-gitflow)
- [Git 工作流选型：GitFlow / GitHub Flow / Trunk-Based 对比](https://m.zpedu.com/it/rjyf/38685.html)
- [社区 Commit 与 PR 规范](https://gitcode.com/jiaxuan_wong/ohos_react_native_0605/blob/main/docs/zh-cn/06-%E7%A4%BE%E5%8C%BA/%E7%A4%BE%E5%8C%BAcommit%E5%92%8Cpr%E8%A7%84%E8%8C%83.md)
- [Google Code Review Playbook（DeployHQ 解读）](https://www.deployhq.com/blog/google-code-review-playbook-deployment-velocity)
- [Google Pigweed: Code Reviews 文档](https://android.googleid.googlesource.com/platform/external/pigweed/+/refs/heads/sdk-release/docs/code_reviews.rst)
- [大厂 Code Review 规范实例（字节飞书团队）](https://datasea.cn/go0218496919.html)
- [从单测到压测：大厂测试金字塔（腾讯云）](https://cloud.tencent.com.cn/developer/article/2584819)
- [AI 工程的 CI/CD：从模型发版到 Skill 灰度完整流水线（腾讯云）](https://cloud.tencent.com.cn/developer/article/2671652)
- [CI/CD 最佳实践（skillstack）](https://github.com/viktorbezdek/skillstack/blob/main/debugging/skills/debugging/references/cicd-best_practices.md)
- [金丝雀/滚动/蓝绿发布差别与关键点（腾讯云）](https://cloud.tencent.cn/developer/article/2003685)
- [部署策略（Microsoft Learn）](https://learn.microsoft.com/zh-cn/training/modules/improve-reliability-deployment/5-strategies)
- [语雀 P0 生产故障复盘学习](https://leetcode.cn/discuss/post/3577963/yu-que-p0-shi-gu-fu-pan-by-liyupi-pudq/)
- [腾讯 SRE 质量运营体系构建与实践研究](https://www.itilchina.cn/achotsao/vip_doc/29189638.html)
- [Secure SDLC Best Practices（TigerGate）](https://www.tigergate.dev/resources/security/secure-sdlc/)
- [AI 语音 Agent 回归测试与 CI/CD（FutureAGI）](https://futureagi.com/blog/voice-agent-regression-testing-ci-cd-2026/)

> 说明：检索完成于 2026-08-27。规范随团队实践持续迭代（版本号递增）。
