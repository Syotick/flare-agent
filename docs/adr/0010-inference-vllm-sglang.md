# ADR-0010 · 推理服务：vLLM 首选 / SGLang 备选

> 状态：accepted
> 日期：2026-08-27
> 决策人：Syotick（用户确认）
> 关联：docs/product/research/01-market-and-tech-research.md §10

## 背景（Context）

自托管推理用于性价比与数据合规场景；先走托管、按需灰度自托管。

## 备选方案（Options）

| 方案 | 优点 | 缺点 |
| --- | --- | --- |
| vLLM | PagedAttention 高吞吐、OpenAI 兼容、生态最大 | GPU 资源需求 |
| SGLang | RadixAttention、结构化输出快 | 生态小于 vLLM |
| TensorRT-LLM | NVIDIA 极致优化 | 开发重、绑卡型 |
| 全托管（百炼/EAS） | 免运维 | 成本与合规权衡 |

## 决策（Decision）

- 选择：**自托管 vLLM 首选、SGLang 备选；初期走托管、自托管按需灰度**
- 理由：吞吐与生态最佳；GPU 成本可控地灰度引入。

## 后果（Consequences）

- 正面：高吞吐、低边际成本、数据不出域。
- 代价：GPU 成本与运维。
- 迁移/回滚：模型网关统一协议，随时切回托管。
