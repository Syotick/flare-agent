# ADR-0013 · 部署平台：阿里云 ACK（K8s）

> 状态：accepted
> 日期：2026-08-27
> 决策人：Syotick（用户确认）
> 关联：docs/product/requirements/01-development-requirements.md §5

## 背景（Context）

高可用、弹性扩展百万级并发、多可用区容灾。

## 备选方案（Options）

| 方案 | 优点 | 缺点 |
| --- | --- | --- |
| ACK（托管 K8s） | 弹性、生态、托管控制面 | K8s 运维知识 |
| ECS 自组 | 灵活 | 无弹性、运维重 |
| 无服务器（SAE/FC） | 免运维 | 长任务/GPU 场景受限 |

## 决策（Decision）

- 选择：**阿里云 ACK + MSE 网关 + 云数据库全家桶；多可用区**
- 理由：托管 K8s + HPA 弹性 + 云原生生态，支撑百万级并发目标。

## 后果（Consequences）

- 正面：弹性伸缩、高可用、可观测打通。
- 代价：K8s 运维由托管缓解。
- 迁移/回滚：Helm 清单化部署，可迁移到其他 K8s。
