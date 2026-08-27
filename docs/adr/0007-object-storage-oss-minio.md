# ADR-0007 · 对象存储：阿里云 OSS（生产）/ MinIO（本地）

> 状态：accepted
> 日期：2026-08-27
> 决策人：Syotick（用户确认）
> 关联：docs/product/requirements/01-development-requirements.md §5

## 背景（Context）

代码快照、技能包、RAG 文档源、沙箱产物、日志归档需要无限扩展的对象存储；用户明确要求用阿里云 OSS。

## 备选方案（Options）

| 方案 | 优点 | 缺点 |
| --- | --- | --- |
| 阿里云 OSS | 无限扩展、生命周期降本、与阿里云打通 | 凭证后续提供 |
| MinIO（本地） | S3 兼容、本地模拟 | 仅本地/小规模 |
| 自建文件系统 | 简单 | 不可扩展、不抗故障 |

## 决策（Decision）

- 选择：**OSS 生产，MinIO 本地模拟；存储层 Provider 抽象**
- 理由：用户指定 OSS；凭证未到先用本地模拟保证可开发。

## 后果（Consequences）

- 正面：存储可无限扩展、成本可治理。
- 代价：Provider 抽象需做好协议兼容（S3 风格）。
- 迁移/回滚：Provider 可切，MinIO/OSS 协议兼容。
