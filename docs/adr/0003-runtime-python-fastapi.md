# ADR-0003 · 运行时语言与 API 框架：Python + FastAPI

> 状态：accepted
> 日期：2026-08-27
> 决策人：Syotick（用户确认）
> 关联：docs/product/requirements/01-development-requirements.md §5

## 背景（Context）

与 LangGraph / ML 生态一致，需要异步高并发 API 与流式（SSE）能力。

## 备选方案（Options）

| 方案 | 优点 | 缺点 |
| --- | --- | --- |
| Python + FastAPI | AI 生态最强、async 高并发、SSE/WS 支持好 | GIL（用异步+进程隔离缓解） |
| TS (Node) | Web 全栈统一 | AI 生态弱于 Python |
| Go | 极致并发 | AI/ML 库稀缺 |

## 决策（Decision）

- 选择：**Python 3.12 + FastAPI**
- 理由：与 LangGraph 同生态；异步 I/O + 流式满足高并发接入需求。

## 后果（Consequences）

- 正面：开发效率与生态最佳。
- 代价：CPU 密集路径用异步 + 水平扩展缓解。
- 迁移/回滚：核心逻辑走 AgentRuntime 抽象，语言替换成本可控。
