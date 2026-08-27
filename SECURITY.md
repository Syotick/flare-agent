# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| latest  | :white_check_mark: |

> 当前处于开发早期（pre-1.0），只维护最新版；进入 1.0 后按版本策略补全。

## Reporting a Vulnerability

请**不要**通过公开 Issue 报告安全漏洞。

请通过 GitHub 的**私有漏洞报告（Private vulnerability reporting）** 或
私有渠道联系维护者，并提供：

- 漏洞类型与严重性评估
- 复现步骤（最小示例）
- 受影响版本与潜在影响

我们会：

1. 在 48 小时内确认收到；
2. 评估并制定修复计划；
3. 修复后通过安全公告/Release Notes 披露。

## Security Expectations (LLM 项目特有)

本项目是 AI Agent 平台，格外关注：

- **Prompt Injection** 防护与工具权限分级
- 不可信代码执行的**沙箱隔离**（Kata/Firecracker 微虚拟化）
- **多租户隔离**与越权防护
- 密钥/凭证管理（KMS / Secrets，禁止入库）
- 供应链安全（依赖锁定 + 扫描）

详见 [开发流程与工程规范 §9](./docs/engineering/01-development-standards.md)。
