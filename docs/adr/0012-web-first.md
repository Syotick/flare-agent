# ADR-0012 · 前端形态：本地 Web 优先

> 状态：accepted
> 日期：2026-08-27
> 决策人：Syotick（用户确认）
> 关联：docs/product/requirements/01-development-requirements.md §5

## 背景（Context）

用户确认产品形态为本地 Web 优先；需要审批与实时流体验。

## 备选方案（Options）

| 方案 | 优点 | 缺点 |
| --- | --- | --- |
| Web 控制台 | 交互丰富、审批/实时流体验好 | 需前后端联调 |
| CLI | 开发者熟悉 | 交互弱 |
| API 优先 | 生态开放 | 无 UI 体验 |

## 决策（Decision）

- 选择：**Web 控制台优先（Vite/React + SSE/WS），预留 CLI/API**
- 理由：用户明确要求本地 Web；审批与实时进度是 Agent 平台核心体验。

## 后果（Consequences）

- 正面：审批/实时进度体验最佳。
- 代价：CLI/API 后置。
- 迁移/回滚：预留 OpenAI 兼容 API，CLI 可后补。
