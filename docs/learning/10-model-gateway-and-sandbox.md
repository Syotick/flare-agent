# Flare Agent · 模型网关与沙箱（实践 + 真理）

> 版本：v1.0 ｜ 日期：2026-08-27 ｜ 状态：draft
> 定位：M4 配套教学文档——真实模型怎么接、function-calling 怎么映射、Agent 怎么安全执行代码。
> 配套：08-技术架构 §3/§5（运行机制/集成）、05-生产部署指南（多供应商/配额/成本）、09-RAG 评测（LLMJudge 依赖本层）。

---

## 1. 模型网关：为什么要有这一层（真理先行）

- 真理：模型调用是 Agent 链路上最贵、最不稳定的环节——统一入口让上层（graph/工具/评测）
  只面对一个 ModelProvider，不感知是 mock、OpenAI、DeepSeek 还是 vLLM。
- 真理：分层职责——
  1. 供应商（OpenAICompatibleProvider）：只做"单次传输 + 解析"，不碰重试/降级；
  2. 网关可靠性（RetryProvider）：网络/超时/5xx 瞬态错误指数退避重试；
  3. 上层策略（M5/M6）：灰度、降级、配额、成本、语义缓存继续在这层叠加。
- 反面（避免）：graph 里直接调某家 SDK——换供应商要改业务代码，且重试逻辑散落各处。

## 2. function-calling 映射：决策契约是唯一交汇点（services/model_gateway/openai_compat.py）

- 内部历史 LLMMessage（role: system/user/assistant/tool）和真实 API 的 wire 格式并不相同。
  映射要点：
  - 出（序列化）：assistant 的 call_tool 决策 JSON 还原成原生 tool_calls（content=null），
    并给随后的 role=tool 消息配对同一个 tool_call_id（OpenAI 强制，缺失 400）；
  - 入（解析）：响应有 tool_calls -> call_tool 决策；纯文本 -> final 决策；
    输出统一成决策 JSON，graph._parse_decision 是唯一解析点（与 mock 同形态）。
- 真理：mock 产决策 JSON、真实模型产原生 tool_calls，二者在 graph 层"长相一致"——
  这正是测试不用连真模型、上线不用改业务代码的原因。
- graph.actor 每轮把工具清单以 tools 参数传给供应商（OpenAI 形态），
  同时保留 system schema 文本（文本型/不支持的供应商仍能靠提示词自主调用）。

## 3. 怎么切真实模型

- 环境变量（12-factor）：
  - FLARE_MODEL_PROVIDER=mock|openai；
  - FLARE_MODEL_API_KEY=sk-...；
  - FLARE_MODEL_BASE_URL=https://api.deepseek.com/v1（DeepSeek/DashScope/vLLM 同协议，只改 base_url）；
  - FLARE_MODEL_NAME=deepseek-chat 等。
- 工厂 build_provider(settings) 按配置装配；未知 provider 抛 ValidationError（fail-fast）。
- 真理：开发 mock、生产真实，同一套测试代码两边都跑——
  差异只在"决策来源"（确定性 vs 真模型），graph/工具/评测全不感知。

## 4. 沙箱：Agent 执行代码的安全底线（services/sandbox/）

- 真理：沙箱三件套是底线——超时（防死循环）、输出上限（防刷爆上下文）、资源上限（防拖垮宿主）；
  外加隔离（生产容器/Kata + 网络隔离），且不可用时 fail-fast，绝不裸跑宿主。
- LocalProcessSandbox（开发）：asyncio 子进程 + wait_for 超时强杀 + 输出截断 +
  POSIX RLIMIT_AS 内存上限（Windows 无 rlimit 自动跳过）；
- DockerSandbox（生产占位）：检测不到 docker 即 SandboxUnavailableError(503)，
  M5 接 --network=none + 内存/CPU 限制 + Kata/Firecracker。
- 工具形态：sandbox_run 工具注册进默认 registry（create_default_registry(sandbox=...)），
  失败转结构化 ToolResult（SANDBOX_TIMEOUT / SANDBOX_EXIT），Agent 观察后重试/换路。

## 5. 端到端回路（M4 目标达成）

    任务输入 -> graph.actor：注入工具 schema + tools 参数 -> 真实供应商（OpenAI 协议）
      -> 原生 tool_calls -> 决策 JSON -> tool_executor：sandbox_run 执行代码
      -> 观察回灌 -> actor 再决策 -> final 收尾；全程 checkpoint 可续、SSE 可看。

- scripts/demo_sandbox.py 演示三层：直接执行 -> 工具 -> Agent 自主调用；
- 测试 17 个：wire 序列化配对、tool_calls 映射、重试恢复/放弃、SSE 流式、沙箱超时/截断/错误、
  Agent 原生工具路径、任务 API 端到端。

## 6. 真理与坑

- 重试只针对瞬态错误（网络/超时/5xx）；4xx 校验错误不重试（重试无意义且可能计费）；
- 流的重试不能安全重放（消费后不可回放），交给上层语义层（M5）；
- tool_call_id 不配对真实 API 直接 400——序列化必须一对一记账；
- 沙箱超时后必须 kill 再 communicate，否则子进程变僵尸；
- 生产沙箱宁可 503 也不降级：悄悄裸跑 = 安全事件。

## 7. 练习

1. 给 RetryProvider 写一个"重试 N 次后抛 ProviderError"的测试，说明它为什么不该重试 4xx。
2. 思考：为什么 mock 也要产"决策 JSON"而不是直接调工具？（提示：graph 只认识一种输入）。
3. 场景题：Agent 被要求"运行这段有死循环的代码"，sandbox_run 会返回什么？Agent 该怎么做？
