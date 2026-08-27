# ADR-0002 · 编排引擎：LangGraph

> 状态：accepted
> 日期：2026-08-27
> 决策人：Syotick（用户确认）
> 关联：docs/product/requirements/01-development-requirements.md §5

## 背景（Context）

需要图式状态机、checkpoint 持久化、interrupt 人机协作、多 Agent 拓扑；LangChain 的 chain 模型不够灵活，自研成本高。

## 备选方案（Options）

| 方案 | 优点 | 缺点 |
| --- | --- | --- |
| LangGraph | 图式状态机、官方持久化、interrupt、多 Agent、生态最大 | 学习曲线、依赖框架演进 |
| CoAgents | 前端实时协作好 | 偏 Web 场景、生态小 |
| OpenAI Agents SDK | 轻量官方 | 长任务持久化弱 |
| 自研 | 完全可控 | 造轮子、成本高 |

## 决策（Decision）

- 选择：**LangGraph（Python）**
- 理由：持久化/中断/多 Agent 能力最契合企业级长任务；上层包 AgentRuntime 抽象防框架锁死。

## 后果（Consequences）

- 正面：可恢复长任务、人机审批、生态完善。
- 代价：框架版本演进需跟踪，靠抽象层兜底。
- 迁移/回滚：AgentRuntime 抽象使引擎可替换。
