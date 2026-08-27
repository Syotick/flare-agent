# ADR-0005 · 会话与缓存：Redis

> 状态：accepted
> 日期：2026-08-27
> 决策人：Syotick（用户确认）
> 关联：docs/product/requirements/01-development-requirements.md §5

## 背景（Context）

需要热会话、限流计数、语义缓存、pub/sub 事件。

## 备选方案（Options）

| 方案 | 优点 | 缺点 |
| --- | --- | --- |
| Redis | 高吞吐、数据结构丰富、集群成熟 | 内存成本需规划 |
| Memcached | 简单 | 数据结构单一、无持久化语义 |
| 自研内存 | 零依赖 | 不可扩展、易失 |

## 决策（Decision）

- 选择：**云 Redis（生产）；本地 Docker Redis**
- 理由：热路径性能 + 多数据结构 + 集群高可用，社区与托管生态成熟。

## 后果（Consequences）

- 正面：会话/限流/缓存一体化。
- 代价：容量与内存成本规划。
- 迁移/回滚：数据访问层抽象，可换其他缓存。
