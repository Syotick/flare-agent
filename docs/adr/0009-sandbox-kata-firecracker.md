# ADR-0009 · 沙箱隔离：Kata/Firecracker 微虚拟化

> 状态：accepted
> 日期：2026-08-27
> 决策人：Syotick（用户确认，要求"最能秀肌肉"的最强方案）
> 关联：docs/product/requirements/01-development-requirements.md §5

## 背景（Context）

不可信代码/命令执行需要强隔离（Prompt 注入放大、越权风险）；用户要求企业级最强的隔离方案。

## 备选方案（Options）

| 方案 | 优点 | 缺点 |
| --- | --- | --- |
| 仅 Docker | 简单 | 共享内核，逃逸风险高 |
| gVisor | 用户态内核、较轻 | 性能与兼容性折中 |
| Kata / Firecracker | 独立微虚拟机、独立内核、隔离最强 | 资源开销与部署复杂 |

## 决策（Decision）

- 选择：**生产 Kata/Firecracker 微虚拟化；本地开发 Docker 降级；SandboxProvider 可插拔**
- 理由：企业级强隔离 + 展示级技术栈；降级模式保证本地可开发。

## 后果（Consequences）

- 正面：最强隔离、可演示、符合企业合规预期。
- 代价：云上部署需支持（后续 ACK/裸金属）。
- 迁移/回滚：Provider 抽象可切回容器级。
