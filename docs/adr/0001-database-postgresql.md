# ADR-0001 · 数据库选型：PostgreSQL

> 状态：accepted
> 日期：2026-08-27
> 决策人：Syotick（用户确认）
> 关联：docs/product/requirements/01-development-requirements.md §5

## 背景（Context）

Agent 平台需要存会话/消息/工具调用 JSON/Agent 状态机快照/审计记录；且我们已选定 LangGraph 做编排，其官方 CheckpointSaver（长任务断点续跑、中断恢复的底座）只原生支持 PostgreSQL（PostgresSaver）与 SQLite，不支持 MySQL。

## 备选方案（Options）

| 方案 | 优点 | 缺点 |
| --- | --- | --- |
| PostgreSQL（RDS） | LangGraph 官方支持；JSONB+GIN 索引强；pgvector/tsvector 兜底 RAG；MVCC 并发稳；事务性 DDL 利于迁移 | 运营细节略复杂于 MySQL（托管后无感） |
| MySQL | 经典 OLTP、国内经验多 | 无 LangGraph 官方支持、JSON 索引弱、无 pgvector、DDL 非事务性 |
| SQLite | 零部署 | 仅本地单机，不满足高并发 |

## 决策（Decision）

- 选择：**云 PostgreSQL（RDS）**
- 理由：生态集成（LangGraph checkpoint）是决定性因素；JSONB 契合 Agent 状态数据；pgvector/tsvector 提供向量与全文兜底。

## 后果（Consequences）

- 正面：与 LangGraph 深度集成；数据建模灵活；一个库覆盖关系+JSON+可选向量。
- 代价：比 MySQL 略高的运维知识门槛。
- 迁移/回滚：本地开发同为 PG，迁移成本低；数据访问层留抽象。
