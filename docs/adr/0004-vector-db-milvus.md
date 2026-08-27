# ADR-0004 · 向量库：Milvus（主选）

> 状态：accepted
> 日期：2026-08-27
> 决策人：Syotick（用户确认）
> 关联：docs/product/requirements/01-development-requirements.md §5

## 背景（Context）

RAG 需要十亿级向量、混合检索、按租户分区隔离与云托管选项。

## 备选方案（Options）

| 方案 | 优点 | 缺点 |
| --- | --- | --- |
| Milvus | 分布式、十亿级、混合检索、云托管可用 | 组件多、运维较重 |
| Qdrant | Rust 高性能、快照、轻量 | 超大集群弱于 Milvus |
| pgvector | 复用 PG、零新组件 | 大向量规模弱 |
| DashVector | 阿里云托管、生态打通 | 绑定云厂商 |

## 决策（Decision）

- 选择：**Milvus 主选；本地开发用 Qdrant/内存向量兜底；小场景 pgvector 兜底**
- 理由：规模与混合检索能力最强；检索层做抽象保持可切换。

## 后果（Consequences）

- 正面：支撑 RAG 规模化与租户分区。
- 代价：组件多，故本地降级方案先行。
- 迁移/回滚：检索客户端抽象，可切 Qdrant/pgvector/DashVector。
