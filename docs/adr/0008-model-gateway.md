# ADR-0008 · 模型网关：自研 OpenAI 兼容（LiteLLM 起步）

> 状态：accepted
> 日期：2026-08-27
> 决策人：Syotick（用户确认）
> 关联：docs/product/requirements/01-development-requirements.md §5

## 背景（Context）

多供应商路由、灰度降级、配额成本、统一协议与审计；默认接入 DeepSeek/通义兼容接口。

## 备选方案（Options）

| 方案 | 优点 | 缺点 |
| --- | --- | --- |
| 自研 | 完全可控、贴合业务 | 开发维护成本 |
| LiteLLM 起步 | 快速上线、多供应商 | 深度定制受限 |
| 直接接供应商 SDK | 最快 | 无统一路由/成本治理 |

## 决策（Decision）

- 选择：**先用 LiteLLM 起步，演进为自研 OpenAI 兼容网关**
- 理由：统一协议 + 多供应商 + 成本配额是企业级刚需；先借开源降低起步成本。

## 后果（Consequences）

- 正面：统一入口、路由/降级/缓存/配额。
- 代价：自研部分需持续投入。
- 迁移/回滚：OpenAI 兼容协议保证客户端无感切换。
