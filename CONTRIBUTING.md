# Contributing to Flare Agent

感谢你愿意为 Flare Agent 贡献力量！本仓库遵循 [开发流程与工程规范](./docs/engineering/01-development-standards.md)，
请在参与前阅读它。以下是与贡献直接相关的要点。

## 如何开始

1. **Fork 本仓库**并克隆到本地。
2. 新建功能分支：`git checkout -b feat/<module>-<description>`（分支命名见规范 §1）。
3. 本地环境：参考各模块 README / docker-compose 一键拉起（MinIO/Redis/PG/向量库）。
4. 开发完成后**必须**：
   - 通过 lint 与单元测试（CI 也会跑）；
   - AI/LLM 改动**必须跑评测（eval）**，并附对比数据（规范 §4.2）；
   - 提交信息遵循 Conventional Commits（规范 §2）。
5. 提交 PR：使用 [PR 模板](./.github/pull_request_template.md)，保持**小 PR**。

## 提交规范（摘录）

```
<type>(<scope>): <subject>
# 例：feat(rag): 多路召回 + RRF 融合
# type: feat|fix|docs|chore|refactor|perf|test|build|ci|security
```

## PR 合入门槛

- [ ] CI 全绿（lint / 测试 / 构建 / 扫描）
- [ ] 有对应测试（unit / integration / eval）
- [ ] 无密钥入库，无未声明的新依赖
- [ ] 关键路径有可观测性埋点
- [ ] 改动说明"为什么"与影响面

## 行为准则

参与即视为同意 [Code of Conduct](./CODE_OF_CONDUCT.md)。

## 提问与讨论

- Bug / 需求：开 Issue（用模板）。
- 讨论：GitHub Discussions。
- 安全问题：走 [SECURITY.md](./SECURITY.md) 的私有通道，**不要**开 Issue。
