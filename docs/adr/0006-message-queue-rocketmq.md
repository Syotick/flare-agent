# ADR-0006 · 消息队列：RocketMQ（生产）/ Kafka 备选

> 状态：accepted
> 日期：2026-08-27
> 决策人：Syotick（用户确认）
> 关联：docs/product/requirements/01-development-requirements.md §5

## 背景（Context）

长任务异步、削峰、事件驱动、任务编排与幂等（outbox）。

## 备选方案（Options）

| 方案 | 优点 | 缺点 |
| --- | --- | --- |
| RocketMQ（阿里云） | 阿里云生态、事务消息、LiteTopic 限流治理经验 | 绑定阿里云（本地用单机/Redis Streams 降级） |
| Kafka | 吞吐极致、社区大 | 无事务消息、运维略重 |
| Redis Streams | 轻量、复用 Redis | 不适合大规模可靠队列 |

## 决策（Decision）

- 选择：**阿里云 RocketMQ 首选，Kafka 备选；本地开发 Redis Streams 降级**
- 理由：阿里云托管 + 事务/削峰能力；本地无云凭证用降级方案不阻塞开发。

## 后果（Consequences）

- 正面：事件驱动、削峰、幂等（outbox）。
- 代价：队列运维由托管承担。
- 迁移/回滚：消息抽象层，可切 Kafka。
