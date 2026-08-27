# ADR-0014 · CI/CD：GitHub Actions

> 状态：accepted
> 日期：2026-08-27
> 决策人：Syotick（用户确认）
> 关联：docs/engineering/01-development-standards.md §5

## 背景（Context）

仓库在 GitHub，需要 lint/test/扫描/构建/发布流水线 + 分支保护。

## 备选方案（Options）

| 方案 | 优点 | 缺点 |
| --- | --- | --- |
| GitHub Actions | 免运维、与仓库一体化、生态丰富 | 私有化部署需适配 |
| GitLab CI | 自托管自由 | 仓库在 GitHub 下集成弱 |
| Jenkins | 成熟 | 运维重、老 |

## 决策（Decision）

- 选择：**GitHub Actions + ACR/ghcr 镜像 + 金丝雀发布（规范见 engineering）**
- 理由：与仓库一体、流程已验证（PR #1/#2 全流程通过）。

## 后果（Consequences）

- 正面：流程自动化、门禁可靠。
- 代价：私有化部署时需迁到自托管 runner。
- 迁移/回滚：Pipeline 以 YAML 定义，可移植。
